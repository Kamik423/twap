#!/usr/bin/env python3

import argparse
import datetime
import json
from pathlib import Path
import traceback

from tabulate import tabulate
import tweepy
from tqdm import tqdm

import matplotlib.pyplot as plt


CONFIG_FILE = Path("key.json")
DATA_FILE = Path("data.json")
USERS_FILE = Path("users.json")

TWEET_COUNT = 50


def get_api() -> tweepy.API:
    config = json.loads(CONFIG_FILE.read_text())
    auth = tweepy.OAuthHandler(config["consumer_key"], config["consumer_secret"])
    auth.set_access_token(config["access_token"], config["access_token_secret"])
    api = tweepy.API(auth)
    return api


def collect():
    data = json.loads(DATA_FILE.read_text())

    api = get_api()

    if len(data) == 0:
        me = api.me()
        friend_ids = api.friends_ids(me.id)
        data = {friend_id: -1 for friend_id in friend_ids}
        DATA_FILE.write_text(json.dumps(data, indent=4))

    data = json.loads(DATA_FILE.read_text())

    for friend_id in tqdm(data):
        if data[friend_id] == -1:
            try:
                timeline = api.user_timeline(friend_id, count=TWEET_COUNT)
                dates = [
                    datetime.datetime.now(),  # they tweeted once a long time ago
                    *[tweet.created_at for tweet in timeline],
                ]
                delta_t = float("inf")
                try:
                    delta_t = (max(dates) - min(dates)).total_seconds()
                except ValueError:  # no tweets
                    pass
                data[friend_id] = delta_t
            except Exception:
                print(traceback.format_exc())
                break
    else:
        print("done.")

    DATA_FILE.write_text(json.dumps(data, indent=4))


def analyze(png: bool = True):
    data = json.loads(DATA_FILE.read_text())
    users = json.loads(USERS_FILE.read_text())
    api = get_api()
    printable_data = {}
    rate_limit_exceeded = False
    for friend_id in tqdm(data):
        tweets_per_hour = 0.0
        try:
            tweets_per_hour = 3600 * TWEET_COUNT / data[friend_id]
        except ZeroDivisionError:
            pass
        if friend_id in users:
            printable_data[users[friend_id]] = tweets_per_hour
        elif rate_limit_exceeded:
            printable_data[str(friend_id)] = tweets_per_hour
        else:
            try:
                friend = api.get_user(friend_id)
                user_name = friend.screen_name
                printable_data[user_name] = tweets_per_hour
                users[friend_id] = user_name
                USERS_FILE.write_text(json.dumps(users, indent=4))
            except tweepy.RateLimitError:
                rate_limit_exceeded = True
                printable_data[str(friend_id)] = tweets_per_hour
    sorted_users = sorted(list(printable_data.keys()), key=lambda k: printable_data[k])

    file_name = "twap_{}." + ("png" if png else "pdf")

    # BARCHART

    plt.barh(
        list(range(len(sorted_users))),
        [printable_data[user] for user in sorted_users],
        align="center",
    )
    plt.yticks(list(range(len(sorted_users))), sorted_users)
    plt.tight_layout()
    fig = plt.gcf()
    fig.set_size_inches(10, 180)
    fig.savefig(file_name.format('bar'), dpi=100)

    # PIECHART

    plt.clf()
    total = sum(printable_data.values())
    cutoff = 0.004 * total
    pieces = {
        key.lstrip("_").rstrip("_"): printable_data[key]
        for key in reversed(sorted_users)
        if printable_data[key] > cutoff
    }
    pieces["other"] = total - sum(pieces.values())
    patches, texts = plt.pie(pieces.values(), shadow=False, startangle=90)
    plt.legend(patches, pieces.keys(), loc="best", fontsize="x-small")
    plt.axis("equal")
    plt.tight_layout()
    fig = plt.gcf()
    fig.set_size_inches(10, 10)
    fig.savefig(file_name.format('pie'), dpi=100)

    # TABLE

    print(tabulate([[user, printable_data[user]] for user in sorted_users[-20:]]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze", help="analyze the data", action="store_true")
    parser.add_argument(
        "--png", help="export a png instead of a pdf", action="store_true"
    )
    args = parser.parse_args()

    if args.analyze:
        analyze(args.png)
    else:
        collect()


if __name__ == "__main__":
    main()
