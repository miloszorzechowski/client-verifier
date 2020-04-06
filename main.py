#!/usr/bin/env python3

import json
import sys
import time

import ts3
import mysql.connector

from mysql.connector import errorcode


def verify_clients(config, cursor, ts3conn):
    while True:
        for client in list(filter(lambda k: k["client_type"] == "0" and config["settings"]["verification_group"] not in k["client_servergroups"].split(",") and set(config["settings"]["ignored_groups"]).intersection(set(client["client_servergroups"].split(","))) and int(k["client_idle_time"]) < 900000, ts3conn.exec_("clientlist", "times", "groups"))):
            cursor.execute("SELECT client_time_spent FROM client_times_spent WHERE client_database_id = %s", client["client_database_id"])
            client_time_spent = cursor.fetchone()

            if not client_time_spent:
                cursor.execute("INSERT INTO client_times_spent (client_database_id, client_time_spent) VALUES (%s, %s)", (client["client_database_id"], 60))
                cnx.commit()
            elif client_time_spent[0] < config["settings"]["required_time_spent"]:
                cursor.execute("UPDATE client_times_spent SET client_time_spent = %s WHERE client_database_id = %s", (client_time_spent[0] + 60, client["client_database_id"]))
                cnx.commit()
            else:
                ts3conn.exec_("servergroupaddclient", sgid=config["settings"]["verification_group"], cldbid=client["client_database_id"])
                cursor.execute("DELETE FROM client_times_spent WHERE client_database_id = %s", (client["client_database_id"]))
                cnx.commit()

        time.sleep(60)


if __name__ == "__main__":
    if sys.version_info < (3, 0):
        sys.exit("Need to run in Python 3.0 or higher")

    try:
        with open("config.json", encoding="utf-8") as f:
            config = json.load(f)
    except IOError:
        sys.exit("Configuration file is not accessible")

    with ts3.query.TS3ServerConnection(config["interface"]["uri"]) as ts3conn:
        print("Created connection to {}".format(ts3conn.host))

        try:
            ts3conn.exec_("login", client_login_name=config["interface"]["username"], client_login_password=config["interface"]["password"])
            print("Logged in to ServerQuery interface as {}".format(config["interface"]["username"]))
        except ts3.query.TS3QueryError as err:
            sys.exit(err)

        try:
            ts3conn.exec_("use", port=config["interface"]["port"])
            print("Selected virtual server with port {}".format(config["interface"]["port"]))
        except ts3.query.TS3QueryError as err:
            sys.exit(err)

        try:
            ts3conn.exec_("clientupdate", client_nickname=config["interface"]["nickname"])
            print('Nickname changed to "{}"'.format(config["interface"]["nickname"]))
        except ts3.query.TS3QueryError as err:
            print(err)

        try:
            cnx = mysql.connector.connect(host=config["database"]["host"], user=config["database"]["user"], password=config["database"]["password"], database=config["database"]["database"])
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print("Something is wrong with your user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                print("Database does not exist")
            else:
                print(err)

        cursor = cnx.cursor(buffered=True)

        verify_clients(config, cursor, ts3conn)
