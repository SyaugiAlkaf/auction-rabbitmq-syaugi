import pika
import json
import time
import random
import operator
import tkinter as tk

class AuctionProvider:
    def __init__(self, auction_id, starting_price, max_duration):
        self.auction_id = auction_id
        self.starting_price = starting_price
        self.max_duration = max_duration
        self.highest_bidder = None
        self.highest_bid = starting_price
        self.bidders = {}

        self.root = tk.Tk()
        self.root.title(f"Auction Provider (Auction ID: {self.auction_id})")

        self.current_bid_label = tk.Label(self.root, text="Current Bid: $")
        self.winning_bid_label = tk.Label(self.root, text="Winning Bid: $")

        self.current_bid_label.pack()
        self.winning_bid_label.pack()

    def start_auction(self):
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()

        exchange_name = 'auction_events'
        channel.exchange_declare(exchange=exchange_name, exchange_type='fanout')

        initial_auction_data = {
            "auction_id": self.auction_id,
            "starting_price": self.starting_price,
        }
        channel.basic_publish(exchange=exchange_name, routing_key='', body=json.dumps(initial_auction_data))
        print(f"Starting Auction (Auction ID: {self.auction_id})")

        result = channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        channel.queue_bind(exchange=exchange_name, queue=queue_name)

        def bid_callback(ch, method, properties, body):
            bid_data = json.loads(body)
            bidder_id = bid_data['bidder_id']
            bid_amount = bid_data['bid_amount']
            self.bidders[bidder_id] = bid_amount
            print(f"{bidder_id} placed a bid: ${bid_amount}")

            self.current_bid_label.config(text=f"Current Bid: ${bid_amount}")
            self.root.update()

        channel.basic_consume(queue=queue_name, on_message_callback=bid_callback, auto_ack=True)

        end_time = time.time() + self.max_duration
        while time.time() < end_time:
            connection.process_data_events()

        print("Auction Ended")
        self.display_winner_and_top_bids()

        connection.close()
        self.root.mainloop()

    def display_winner_and_top_bids(self):
        if self.bidders:
            sorted_bids = sorted(self.bidders.items(), key=operator.itemgetter(1), reverse=True)
            winner_bidder, winning_bid = sorted_bids[0]
            self.highest_bidder = winner_bidder
            self.highest_bid = winning_bid
            self.winning_bid_label.config(text=f"Winning Bid: ${winning_bid}")

            print(f"Winner: {winner_bidder}, Winning Bid: ${winning_bid}")
            print("Top 5 Bids:")
            for i, (bidder, bid_amount) in enumerate(sorted_bids[:5], start=1):
                print(f"{i}. {bidder}: ${bid_amount}")
        else:
            print("No bids received.")

if __name__ == '__main__':
    auction_id = "12345"
    starting_price = 100
    max_duration = 5

    provider = AuctionProvider(auction_id, starting_price, max_duration)
    provider.start_auction()
