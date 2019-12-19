# W205 - Data Engineering - Project 3: Understanding User Behavior

By: Nick Sylva

## Summary

This repository provides a detailed demonstration of how to spin up a simple data pipeline for the purpose of answering business questions about user behavior for an imagined trade-based fantasy game. The topics demonstrated consist of the following:

1. Spinning Up an API and Pipeline
2. Building the Trade Engine API Using Flask
3. Keeping Track of Player States Using Redis
4. Logging Events to Kafka
5. Landing Player State and Trade Data As It Occurs in HDFS using Kafka and Spark Streaming
6. Simulating Player Creation and Trade Activity with Apache Bench and Python
7. Querying the Data with Presto to Answer Business Questions.

## Business Questions and Purpose

It is important to ground any data pipeline and questions in the context of the business. For this project, we are looking at player states and trade data within our game. We would like to understand how players interact with each other and how the item economy works in our game. These data could also help identity exploitative behavior in the game.

The following business questions are answered and their corresponding Spark SQL is demonstrated:

1. How many trades occurred?
2. Which item is traded most often?
4. Which player has the most diverse inventory (greatest number of different items) at any given time?
5. Which player has the greatest gold value in terms of items in their inventory at any given time?

## Repository Directory

The root of this repository contains the following:

* */data*/ [directory]: contains project data
  * *names.txt* [file]: text file containing a list of possible player names.
  * *test_data.json* [file]: JSON file used for executing a complex test trade.
  * *test_data_simple.json* [file]: JSON file used for executing a simple test trade.
  * *test_player.json* [file]: JSON file used for random player generation.
* */src/* [directory]: contains source code for Trade Engine API, trade simulation, inventory generation, and Spark Streaming jobs.
  * *\__\_init\_\__.py* [file]: empty python file that tells the interpreter to see this directory as a package.
  * *classes/* [directory ]: contains source code for the classes used in the Trade Engine API
    * *\__\_init\_\__.py* [file]: empty python file that tells the interpreter to see this directory as a package.
    * *Trade.py* [file]: python file containing class definition for the Trade object in the Trade Engine API.
    * *Player.py* [file]: python file containing class definition for the Player object in the Trade Engine API.
    * *Inventory.py* [file]: python file containing class definition for the Inventory object in the Trade Engine API.
    * *Item.py* [file]: python file containing class definition for the Item object in the Trade Engine API.
  * *inventory_generation/* [directory]: contains code for generating inventories based on specific class choice.
    * *\__\_init\_\__.py* [file]: empty python file that tells the interpreter to see this directory as a package.
    * *generate_inventory.py* [file]: python file dictating random class distribution and inventory assignment code.
    * *class_default_inventories.json* [file]: JSON file defining the defaul inventories for each class.
  * *trade_simulation.py* [file]: python file that simulates 10,000 random trades.
  * *write_player_state_from_stream.py* [file]: Spark Streaming job file that filters event stream for player_state events and writes to HDFS.
  * *write_trade_from_stream.py* [file]: Spark Streaming job file that filters event stream for trade events and writes to HDFS.
* *\__\_init\_\__.py* [file]: empty python file that tells the interpreter to see this directory as a package.
* *.gitignore* [file]: file dictating which local files should not be tracked.
* *app.py* [file]: python file containing main Flask Trade Engine API app.
* */docker-compose.yml* [file]: contains configuration information for the Docker containers used in this project
* */nick_sylva_report.md* [file]: main report that provides detailed step-by-step process instructions, queries, and answers to the business questions stated above.
