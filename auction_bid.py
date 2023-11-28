import pika
import json
import tkinter as tk
import tkinter.messagebox as messagebox
from datetime import datetime
import threading


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

        self.quit_button = tk.Button(self.root, text="Quit", command=self.quit_bidding, state=tk.DISABLED)
        self.quit_button.pack()

        self.auction_status = ""
        self.starting_bid = ""
        self.highest_bid = ""
        self.time_left = ""
        self.bid_winner = ""

        self.submitted = False  # Flag to track if ID is submitted

        # Establish RabbitMQ connection and channel
        self.setup_rabbitmq()

        self.root.mainloop()

    def setup_rabbitmq(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(self.amqp_url))
        self.channel = self.connection.channel()

    def submit_id(self):
        if not self.submitted:
            self.bidder_id = self.id_entry.get()
            self.submitted = True
            self.auction_ui()
            self.submit_button.config(state=tk.DISABLED)
            self.quit_button.config(state=tk.NORMAL)
        else:
            messagebox.showinfo("Already Submitted", "You've already submitted your ID.")

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
        self.selected_pub_queue = ""

    def select_queue(self, queue):
        self.selected_queue = queue
        self.selected_pub_queue = queue + "_info"
        print(f"Selected queue: {queue}")
        print(f"Selected queue: {self.selected_pub_queue}")

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
            if self.channel.is_open:
                method_frame = self.channel.queue_declare(queue=queue_name, passive=True)
                return method_frame.method.queue == queue_name
            else:
                # Re-establish the connection and channel if closed
                self.setup_rabbitmq()
                return False
        except pika.exceptions.ChannelClosedByBroker as e:
            if e.args[0] == 404:
                return False
            else:
                raise e

    def start_message_consumption(self):
        def callback(ch, method, properties, body):
            print("Received info from the queue...")

            # Your callback logic here...

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
                self.channel.basic_publish(exchange='auction_direct_exchange', routing_key=self.selected_queue,
                                           body=json.dumps(bid_data))
                print(
                    f"{self.bidder_id} Placed a Bid of ${bid_amount} at {bid_timestamp} to Queue {self.selected_queue}")
            else:
                print("Auction is not running. Unable to place bid.")

        self.channel.basic_consume(
            queue=self.selected_pub_queue,
            on_message_callback=callback,
            auto_ack=True
        )
        self.channel.start_consuming()

    def display_queue_info(self):
        print("Displaying queue info...")

        def callback(ch, method, properties, body):
            print("Updating info...")

            # If body is bytes, decode it to a string for readability
            body_str = body.decode('utf-8')
            print("Body (decoded):", body_str)

            info_data = json.loads(body.decode())
            auction_status = info_data.get('auction_isRunning')
            starting_bid = info_data.get('starting_bid')
            highest_bid = info_data.get('highest_bid')
            time_left = info_data.get('time_left_seconds')
            bid_winner = info_data.get('highest_bidder')

            self.root.title(f"Queue Info: {self.selected_queue}")

            info_text = f"Auction Status: {auction_status}\n"
            info_text += f"Starting Bid: {starting_bid}\n"
            info_text += f"Highest Bid: {highest_bid}\n"
            info_text += f"Time Left to Bid: {time_left} seconds\n"
            info_text += f"Bid Winner ID: {bid_winner}\n"

            # Clear previous info labels before updating
            for widget in self.root.winfo_children():
                if isinstance(widget, tk.Label):
                    widget.destroy()

            tk.Label(self.root, text=info_text).pack()

        def consume_messages():
            self.channel.basic_consume(queue=self.selected_pub_queue, on_message_callback=callback, auto_ack=True)
            self.channel.start_consuming()

        # Start consuming messages in a separate thread
        consume_thread = threading.Thread(target=consume_messages)
        consume_thread.daemon = True  # Allow the program to exit even if the thread is running
        consume_thread.start()

    def bid_ui(self):
        self.bid_label = tk.Label(self.root, text="Bid amount:")
        self.bid_label.pack()

        self.bid_entry = tk.Entry(self.root)
        self.bid_entry.pack()

        self.bid_button = tk.Button(self.root, text="Place Bid", command=self.place_bid)
        self.bid_button.pack()

    def place_bid(self):
        consume_thread = threading.Thread(target=self.start_message_consumption)
        consume_thread.daemon = True
        consume_thread.start()

    def quit_bidding(self):
        if messagebox.askyesno("Quit Bidding", "Are you sure you want to quit bidding?"):
            self.root.destroy()

if __name__ == '__main__':
    amqp_url = "amqps://zhmbpgxq:2IT7TpRnUaF62oQxjIcupAvAMxkuHvHo@albatross.rmq.cloudamqp.com/zhmbpgxq"

    bidder = AuctionBidder(amqp_url)
