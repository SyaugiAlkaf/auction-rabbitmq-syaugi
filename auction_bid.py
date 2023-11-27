import pika
import json
import tkinter as tk
import tkinter.messagebox as messagebox
from datetime import datetime

class AuctionBidder:
    def __init__(self, amqp_url):
        self.amqp_url = amqp_url
        self.root = tk.Tk()
        self.root.geometry('300x350')

        self.id_label = tk.Label(self.root, text="Enter your ID:")
        self.id_label.pack()

        self.id_entry = tk.Entry(self.root)
        self.id_entry.pack()

        self.submit_button = tk.Button(self.root, text="Submit", command=self.submit_id)
        self.submit_button.pack()
        self.root.mainloop()

        self.auction_status = ""
        self.starting_bid = ""
        self.highest_bid = ""
        self.time_left = ""
        self.bid_winner = ""

    def submit_id(self):
        self.bidder_id = self.id_entry.get()
        self.auction_ui()

    def auction_ui(self):
        self.root.title(f"Auction Bidder: {self.bidder_id}")

        self.exchange_label = tk.Label(self.root, text="Select Queue:")
        self.exchange_label.pack()

        self.mobil_button = tk.Button(self.root, text="Mobil", command=lambda: self.select_queue("mobil"))
        self.mobil_button.pack()

        self.motor_button = tk.Button(self.root, text="Motor", command=lambda: self.select_queue("motor"))
        self.motor_button.pack()

        self.rumah_button = tk.Button(self.root, text="Rumah", command=lambda: self.select_queue("rumah"))
        self.rumah_button.pack()

        self.selected_queue = ""

    def select_queue(self, queue):
        self.selected_queue = queue
        print(f"Selected queue: {queue}")

        # Check if the desired queue exists in the exchange before proceeding
        if self.check_queue_exists(queue):
            for widget in self.root.winfo_children():
                widget.destroy()

            self.display_queue_info()
            self.bid_ui()
        else:
            messagebox.showinfo("Queue Not Found", f"The auction for '{queue}' has not started yet.")

    def check_queue_exists(self, queue_name):
        try:
            params = pika.URLParameters(self.amqp_url)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            method_frame = channel.queue_declare(queue=queue_name, passive=True)

            connection.close()

            return method_frame.method.queue == queue_name
        except pika.exceptions.ChannelClosedByBroker as e:
            if e.args[0] == 404:
                return False
            else:
                raise e

    def display_queue_info(self):
        def update_info():
            params = pika.URLParameters(self.amqp_url)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()

            method_frame, header_frame, body = channel.basic_get(queue='info')

            if method_frame and method_frame.NAME != 'Basic.GetEmpty':
                info_data = json.loads(body.decode())
                self.auction_status = info_data.get('auction_isRunning')
                self.starting_bid = info_data.get('starting_bid')
                self.highest_bid = info_data.get('highest_bid')
                self.time_left = info_data.get('time_left_seconds')
                self.bid_winner = info_data.get('highest_bidder')

                self.root.title(f"Queue Info: {self.selected_queue}")

                info_text = f"Auction Status: {self.auction_status}\n"
                info_text += f"Starting Bid: {self.starting_bid}\n"
                info_text += f"Highest Bid: {self.highest_bid}\n"
                info_text += f"Time Left to Bid: {self.time_left} seconds\n"
                info_text += f"Bid Winner ID: {self.bid_winner}\n"

                info_label.config(text=info_text)
            else:
                print("No information available about the auction.")

            connection.close()
            self.root.after(1000, update_info)  # Schedule the next update after 1 second

        info_label = tk.Label(self.root, text="", justify=tk.LEFT)
        info_label.pack()

        update_info()

    def bid_ui(self):
        self.bid_label = tk.Label(self.root, text="Bid amount:")
        self.bid_label.pack()

        self.bid_entry = tk.Entry(self.root)
        self.bid_entry.pack()

        self.bid_button = tk.Button(self.root, text="Place Bid", command=self.place_bid)
        self.bid_button.pack()

    def place_bid(self):
        params = pika.URLParameters(self.amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        # Declaring exchange (if not already declared)
        channel.exchange_declare(exchange='auction_direct_exchange', exchange_type='direct')

        # Retrieve information about the auction from the 'info' queue
        method_frame, header_frame, body = channel.basic_get(queue='info')

        if method_frame and method_frame.NAME == 'Basic.GetEmpty':
            print("No information available about the auction.")
            connection.close()
            return

        info_data = json.loads(body)
        auction_status = info_data.get('auction_isRunning')

        if auction_status == "Running":
            bid_amount = self.bid_entry.get()
            bid_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            bid_data = {
                "bidder_id": self.bidder_id,
                "bid_amount": bid_amount,
                "bid_timestamp": bid_timestamp,
            }

            # Publishing bid data to the specified exchange and routing key (queue)
            channel.basic_publish(exchange='auction_direct_exchange', routing_key=self.selected_queue,
                                  body=json.dumps(bid_data))
            print(f"{self.bidder_id} Placed a Bid of ${bid_amount} at {bid_timestamp} to Queue {self.selected_queue}")
        else:
            print("Auction is not running. Unable to place bid.")

        # Closing the connection
        connection.close()

if __name__ == '__main__':
    amqp_url = "amqps://zhmbpgxq:2IT7TpRnUaF62oQxjIcupAvAMxkuHvHo@albatross.rmq.cloudamqp.com/zhmbpgxq"
    
    bidder = AuctionBidder(amqp_url)
