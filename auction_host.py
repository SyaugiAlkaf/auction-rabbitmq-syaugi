import pika
import json
import time
import operator
import tkinter as tk
from tkinter import messagebox
import os

class AuctionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auction App")
        self.root.geometry('300x400')

        self.auction_status_label = tk.Label(root, text="Auction Status: Not Running")
        self.auction_status_label.pack()

        self.current_bid_label = tk.Label(root, text="Current Bid: $")
        self.current_bid_label.pack()

        self.winning_bid_label = tk.Label(root, text="Winning Bid: $")
        self.winning_bid_label.pack()

        self.time_left_label = tk.Label(root, text="Time Left: ")
        self.time_left_label.pack()

        # # Entry widgets for user input
        # self.label_nama = tk.Label(root, text="Nama Barang:")
        # self.label_nama.pack()
        # self.entry_nama = tk.Entry(root)
        # self.entry_nama.pack()

        self.exchange_label = tk.Label(self.root, text="Pilih Barang Lelang:")
        self.exchange_label.pack()

        self.mobil_button = tk.Button(self.root, text="Mobil", command=lambda: self.select_queue("mobil"))
        self.mobil_button.pack()

        self.motor_button = tk.Button(self.root, text="Motor", command=lambda: self.select_queue("motor"))
        self.motor_button.pack()

        self.rumah_button = tk.Button(self.root, text="Rumah", command=lambda: self.select_queue("rumah"))
        self.rumah_button.pack()

        self.label_harga = tk.Label(root, text="Harga Barang (Rp):")
        self.label_harga.pack()
        self.entry_harga = tk.Entry(root)
        self.entry_harga.pack()

        self.label_waktu = tk.Label(root, text="Waktu Lelang (detik):")
        self.label_waktu.pack()
        self.entry_waktu = tk.Entry(root)
        self.entry_waktu.pack()

        # Button to start auction
        self.start_button = tk.Button(root, text="Start Auction", command=self.start_auction)
        self.start_button.pack()

        self.selected_queue = ""

        self.auction_running = False
        self.bidders = {}
        self.highest_bidder = None
        self.highest_bid = 0
        self.auction_id = None
        self.amqp_url = os.environ.get('albatross-01.rmq.cloudamqp.com',
                                        'amqps://zhmbpgxq:2IT7TpRnUaF62oQxjIcupAvAMxkuHvHo@albatross.rmq.cloudamqp.com/zhmbpgxq')

        self.root.after(1000, self.update_auction_status)

    def select_queue(self, queue):
        self.selected_queue = queue
        print(f"Selected Queue: {queue}")

    def start_auction(self):
        if self.selected_queue == "":
            print("Please select an queue first.")
            return

        # nama_barang = self.entry_nama.get()
        nama_barang = self.selected_queue
        harga_barang = self.entry_harga.get()
        waktu_lelang = self.entry_waktu.get()

        if not nama_barang or not harga_barang or not waktu_lelang:
            messagebox.showerror("Error", "Please fill in all fields.")
            return

        self.auction_id = nama_barang
        self.auction_running = True
        self.auction_status_label.config(text="Auction Status: Running")

        params = pika.URLParameters(self.amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.exchange_declare(exchange='auction_direct_exchange', exchange_type='direct')

        initial_auction_data = {
            "auction_id": nama_barang,
            "starting_price": int(harga_barang),
        }
        channel.basic_publish(exchange='auction_direct_exchange',
                              routing_key=nama_barang,
                              body=json.dumps(initial_auction_data))
        print(f"Starting Auction (Auction ID: {nama_barang})")

        result = channel.queue_declare(queue=nama_barang, exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='auction_direct_exchange', queue=queue_name, routing_key=nama_barang)

        def bid_callback(ch, method, properties, body):
            bid_data = json.loads(body)
            bidder_id = bid_data.get('bidder_id')
            bid_amount = bid_data.get('bid_amount')

            if bidder_id and bid_amount:
                self.bidders[bidder_id] = bid_amount
                print(f"{bidder_id} placed a bid: ${bid_amount}")

                # Check if the incoming bid is higher than the current highest bid
                if bid_amount > self.highest_bid:
                    self.highest_bid = bid_amount
                    self.highest_bidder = bidder_id

                self.current_bid_label.config(text=f"Current Bid: ${bid_amount}")
                self.root.update()
            else:
                print("Invalid bid data received")

        channel.basic_consume(queue=queue_name, on_message_callback=bid_callback, auto_ack=True)

        end_time = time.time() + float(waktu_lelang)
        while time.time() < end_time:
            time_left = int(end_time - time.time())
            self.send_highest_bid_time(nama_barang, harga_barang, end_time)
            self.time_left_label.config(text=f"Time Left: {time_left} seconds")
            self.root.update()
            connection.process_data_events()

        print("Auction Ended")
        self.display_winner_and_top_bids()
        connection.close()
        self.auction_running = False
        self.auction_status_label.config(text="Auction Status: Not Running")
        self.time_left_label.config(text=f"Time Left: 0 seconds")
        self.send_winner(nama_barang, harga_barang, end_time)

    def send_winner(self, nama_barang, harga_barang, end_time):
        params = pika.URLParameters(self.amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.exchange_declare(exchange="auction_direct_exchange", exchange_type='direct')
        result = channel.queue_declare(queue='info', exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='auction_direct_exchange', queue=queue_name, routing_key='info')

        time_left = int(end_time - time.time())
        if time_left < 0:
            time_left = 0  # Ensure it's not negative

        highest_bid_data = {
            "auction_isRunning": "Not Running",
            "auction_id": nama_barang,
            "starting_bid": harga_barang,
            "highest_bid": self.highest_bid,
            "highest_bidder": self.highest_bidder,
            "time_left_seconds": time_left
        }
        channel.basic_publish(
            exchange="auction_direct_exchange",
            routing_key='info',
            body=json.dumps(highest_bid_data)
        )
        print(f"Data sent to Host's exchange [auction_isRunning: Running, auction_id: {nama_barang}, highest_bid: {self.highest_bid}, highest_bidder: {self.highest_bidder}, time_left_seconds: {time_left}]")
        connection.close()

    def send_highest_bid_time(self, nama_barang, harga_barang, end_time):
        params = pika.URLParameters(self.amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.exchange_declare(exchange="auction_direct_exchange", exchange_type='direct')
        result = channel.queue_declare(queue='info', exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange='auction_direct_exchange', queue=queue_name, routing_key='info')

        time_left = int(end_time - time.time())
        if time_left < 0:
            time_left = 0  # Ensure it's not negative

        highest_bid_data = {
            "auction_isRunning": "Running",
            "auction_id": nama_barang,
            "starting_bid": harga_barang,
            "highest_bid": self.highest_bid,
            "highest_bidder": None,
            "time_left_seconds": time_left
        }
        channel.basic_publish(
            exchange="auction_direct_exchange",
            routing_key='info',
            body=json.dumps(highest_bid_data)
        )
        print(f"Data sent to Host's exchange [auction_isRunning: Running, auction_id: {nama_barang}, highest_bid: {self.highest_bid}, highest_bidder: {self.highest_bidder}, time_left_seconds: {time_left}]")
        connection.close()

    def display_winner_and_top_bids(self):
        if self.bidders:
            sorted_bids = sorted(self.bidders.items(), key=operator.itemgetter(1), reverse=True)
            self.highest_bidder, self.highest_bid = sorted_bids[0]
            winner_label = tk.Label(self.root, text=f"Winning Bidder: {self.highest_bidder}")
            winner_label.pack()
            self.winning_bid_label.config(text=f"Winning Bid: ${self.highest_bid}")

            print(f"Winner: {self.highest_bidder}, Winning Bid: ${self.highest_bid}")
            print("Top 5 Bids:")
            for i, (bidder, bid_amount) in enumerate(sorted_bids[:5], start=1):
                print(f"{i}. {bidder}: ${bid_amount}")
        else:
            print("No bids received.")

    def update_auction_status(self):
        if self.auction_running:
            self.auction_status_label.config(text="Auction Status: Running")
        else:
            self.auction_status_label.config(text="Auction Status: Not Running")

        self.root.after(1000, self.update_auction_status)


if __name__ == "__main__":
    root = tk.Tk()
    app = AuctionApp(root)
    root.mainloop()
