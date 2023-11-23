import pika
import json
import threading
import random
import time
import os
from datetime import datetime

class AuctionBidder:
    def __init__(self, auction_id, bidder_id, amqp_url):
        self.auction_id = auction_id
        self.bidder_id = bidder_id
        self.amqp_url = amqp_url

    def place_bid(self):
        params = pika.URLParameters(self.amqp_url)
        connection = pika.BlockingConnection(params)
        channel = connection.channel()

        channel.exchange_declare(exchange='auction_events', exchange_type='fanout')

        while True:
            bid_amount = random.randint(90, 10000)
            bid_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            bid_data = {
                "auction_id": self.auction_id,
                "bidder_id": self.bidder_id,
                "bid_amount": bid_amount,
                "bid_timestamp": bid_timestamp,
            }
            channel.basic_publish(exchange='auction_events', routing_key='', body=json.dumps(bid_data))
            print(f"{self.bidder_id} placed a bid: ${bid_amount} at {bid_timestamp}")

            time.sleep(2)  # Bid every 2 seconds

if __name__ == '__main__':
    auction_id = "12345"

    amqp_url = os.environ.get('albatross-01.rmq.cloudamqp.com',
                              'amqps://zhmbpgxq:2IT7TpRnUaF62oQxjIcupAvAMxkuHvHo@albatross.rmq.cloudamqp.com/zhmbpgxq')

    bidders = [
        AuctionBidder(auction_id, "Bidder_1", amqp_url),
        AuctionBidder(auction_id, "Bidder_2", amqp_url),
        AuctionBidder(auction_id, "Bidder_3", amqp_url),
        AuctionBidder(auction_id, "Bidder_4", amqp_url),
        AuctionBidder(auction_id, "Bidder_5", amqp_url),
    ]

    for bidder in bidders:
        threading.Thread(target=bidder.place_bid).start()
