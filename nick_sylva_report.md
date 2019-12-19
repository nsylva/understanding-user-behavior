# W205 Project 3 

## Understanding User Behavior

### Nick Sylva 12/10/2019

User behavior in rich, multiplayer online games like ours can tell us a lot about how players are playing are game, which mechanics are being abused, and how we can make the game better. This project focused on tracking user-behavior within our trading engine to specifically understand the in-game economy. Which items are traded most often? How often are trades with imbalanced value (a sign of cheating) performed? These are just two examples of questions we can answer with an analytics pipeline built off of our trade engine API. 

This document will cover the following topics:

0. Spinning Up the API and Pipeline

1. Building the Trade Engine API Using Flask
2. Keeping Track of Player States Using Redis
3. Logging Events to Kafka
4. Landing Player State and Trade Data As It Occurs in HDFS using Kafka and Spark Streaming
5. Simulating Player Creation and Trade Activity with Apache Bench and Python
6. Querying the Data with Presto to Answer Business Questions.

Most of the document entails technical description of various aspects of the Trade Engine API and the Analytics Pipeline. If you are just interested in the commands necessary to run everything, execute the commands listed in the **Commands** sub-section at the end of each main section *in consecutive order* from the root of the project directory (`/w205/project-3-nsylva`).

### 0. Spinning Up the API and Pipeline

The Trade Engine API and Analytics Pipeline can be easily and neatly spun up using Docker and the tool `docker-compose`. The pipeline components can be linked together using the `docker-compose.yml` file below:

```yaml
---
version: '2'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 32181
      ZOOKEEPER_TICK_TIME: 2000
    expose:
      - "2181"
      - "2888"
      - "32181"
      - "3888"
    extra_hosts:
      - "moby:127.0.0.1"

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:32181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    expose:
      - "9092"
      - "29092"
    extra_hosts:
      - "moby:127.0.0.1"

  cloudera:
    image: midsw205/hadoop:0.0.2
    hostname: cloudera
    expose:
      - "8020" # nn
      - "8888" # hue
      - "9083" # hive thrift
      - "10000" # hive jdbc
      - "50070" # nn http
    ports:
      - "8888:8888"
    extra_hosts:
      - "moby:127.0.0.1"

  spark:
    image: midsw205/spark-python:0.0.6
    stdin_open: true
    tty: true
    volumes:
      - ~/w205:/w205
    expose:
      - "8888"
    ports:
      - "8889:8888" # 8888 conflicts with hue
    depends_on:
      - cloudera
    environment:
      HADOOP_NAMENODE: cloudera
      HIVE_THRIFTSERVER: cloudera:9083
    extra_hosts:
      - "moby:127.0.0.1"
    command: bash

  presto:
    image: midsw205/presto:0.0.1
    hostname: presto
    volumes:
      - ~/w205:/w205
    expose:
      - "8080"
    environment:
      HIVE_THRIFTSERVER: cloudera:9083
    extra_hosts:
      - "moby:127.0.0.1"

  mids:
    image: midsw205/base:0.1.9
    stdin_open: true
    tty: true
    volumes:
      - ~/w205:/w205
    expose:
      - "5000"
    ports:
      - "5000:5000"
    extra_hosts:
      - "moby:127.0.0.1"

  redis:
    image: redis:latest
    expose:
      - "6379"
    ports:
      - "6379:6379"
    extra_hosts:
      - "moby:127.0.0.1"
```

The images used for this pipeline are:

* `zookeeper`: coordinates Apache services, Hadoop, Kafka, and Spark
* `kafka`: message queuing
* `cloudera`: handles Hadoop distributed file storage (HDFS)
* `spark`: data streaming and transformation
* `mids`: Linux image to run the Flask server and execute benchmarking commands.
* `redis`: in-memory cache for keeping track of player state without having to read from HDFS every time a trade is requested.

#### 0.1 Commands

Starting this pipeline is as simple as executing the following commands in the directory where the `docker-compose.yml` file is stored:

```bash
docker-compose up -d
docker-compose exec mids pip install redis #container does not come with this package by default.
```

### 1. Building the Trade Engine API Using Flask

Flask allows for the easy deployment of web-based apps and simple APIs. For the purpose of this project, we are assuming that the backend of the Trade Engine is utilizing this same API and that the code included represents the trade-related and character creation components. In production, there would be many more routes capturing information related to numerous other actions that players take.

The full code for our Flask app is stored in the `app.py` file at the root of the directory. Individual helper files, such as class definitions and inventory generation code, can be found within the `src` directory within the root directory. 

The two routes for this project are `create_player` and `trade`, included below:

```python
@app.route('/create_player',methods = ['PUT'])
def create_player():
   
    creation_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S.%f")
    #grab default inventory state from file
    #default_state = json.load('./data/new_player_default_state.json')
    
    # get data from the user that created a new player. Should only contain username and  desired class. Both will be automatically generated if not provided.
    player_data = request.json
    #generate a default inventory based on item randomization or specified character class
    if type(player_data) is  None:
        player_class, player_inventory, player_gold = generate_inventory()
        player_username = pick_username()
    elif type(player_data) == dict:
        player_class, player_inventory, player_gold = generate_inventory(player_data['player_class'])
        if 'username' not in player_data.keys():
            player_username = pick_username()
        else:
            player_username = player_data['username']
    else:
        return """Player creation failed. 'username' and 'player_class' are required
        parameters. Send data as JSON.\n"""
    
    #get the max existing id from the Redis cache
    try:
        all_ids = redis_host.keys()
        numeric_ids = [int(id) for id in all_ids]
        max_existing_id = sorted(numeric_ids,reverse=True)[0]
        new_id = int(max_existing_id) + 1
    except IndexError:
        new_id = 0
    player_data['player_id'] = new_id
    player_data['inventory'] = player_inventory
    player_data['gold'] = player_gold
    player_data['player_class'] = player_class
    player_data['username'] = player_username
    
    # push the new player state to Redis
    set_player_inventory_state(new_id,json.dumps(player_data))
    
    # generate a state_id for HDFS storage and build out a flat array of player states
    state_id = create_state_id(player_username,new_id,creation_time)
    player_states = [construct_state_dict(state_id,
                                            new_id,
                                            player_username,
                                            player_class,
                                            creation_time,
                                            player_inventory['max_capacity'],
                                            player_inventory['current_capacity'],
                                            i,
                                            player_gold) for i in player_data['inventory']['items']]

    # log player creation to Kafka
    for player_state in player_states:
        log_to_kafka('events',player_state)
   
    # return a success message
    success_message = 'New %s (player_id = %i) with username = %s created.\n'%(player_class,new_id,player_data['username'])
    print(success_message)
    return success_message

@app.route('/trade', methods = ['POST'])
def trade():
    trade_time = datetime.now().strftime("%m/%d/%Y, %H:%M:%S.%f")
    trade_data = request.json

    #create a trade object
    working_trade = Trade(trade_data,redis_host)
    #validate trade
    valid_trade, fail_reason = working_trade.valid, working_trade.fail_reason
    #generate trade_id
    trade_id = create_trade_id(working_trade.player_1.username,working_trade.player_1.player_id,working_trade.player_2.username,working_trade.player_2.player_id,trade_time)
    
    if valid_trade:
        #update inventories and gold counts
        working_trade.execute_trade()
        player_1_dict = working_trade.player_1.to_dict()
        player_2_dict = working_trade.player_2.to_dict()
        # push new inventory and gold states for each player to redis cache
        player_1_updated_state = json.dumps(player_1_dict)
        player_2_updated_state = json.dumps(player_2_dict)
        set_player_inventory_state(working_trade.player_1.player_id, player_1_updated_state)
        set_player_inventory_state(working_trade.player_2.player_id, player_2_updated_state)
        
        # send the player states to Kafka
        player_1_state_id = create_state_id(player_1_dict['username'],player_1_dict['player_id'],trade_time)
        player_2_state_id = create_state_id(player_2_dict['username'],player_2_dict['player_id'],trade_time)

        '''state_id,player_id,username,player_class,timestamp,inventory_max_capacity,inventory_current_capacity,item_held, gold'''
        player_1_states = [construct_state_dict(player_1_state_id,
                                                player_1_dict['player_id'],
                                                player_1_dict['username'],
                                                player_1_dict['player_class'],
                                                trade_time,
                                                player_1_dict['inventory']['max_capacity'],
                                                player_1_dict['inventory']['current_capacity'],
                                                i,
                                                player_1_dict['gold']) for i in player_1_dict['inventory']['items']]

        player_2_states = [construct_state_dict(player_2_state_id,
                                                player_2_dict['player_id'],
                                                player_2_dict['username'],
                                                player_2_dict['player_class'],
                                                trade_time,
                                                player_2_dict['inventory']['max_capacity'],
                                                player_2_dict['inventory']['current_capacity'],
                                                i,
                                                player_2_dict['gold']) for i in player_2_dict['inventory']['items']]

        for player_1_state in player_1_states:
            log_to_kafka('events',player_1_state)

        for player_2_state in player_2_states:
            log_to_kafka('events',player_2_state)

        trade = working_trade.to_dict()
        player_1_trades = [construct_trade_dict(trade_id,
                                                trade['player_1']['player_id'],
                                                trade_time,
                                                i,
                                                trade['player_1']['gold_traded'],
                                                valid_trade,
                                                fail_reason) for i in trade['player_1']['items_traded']]
        player_2_trades = [construct_trade_dict(trade_id,
                                                trade['player_2']['player_id'],
                                                trade_time,
                                                i,
                                                trade['player_2']['gold_traded'],
                                                valid_trade,
                                                fail_reason) for i in trade['player_2']['items_traded']]
        
        #log the failed trade to kafka
        for player_1_trade in player_1_trades:
            log_to_kafka('events',player_1_trade)
        for player_2_trade in player_2_trades:
            log_to_kafka('events',player_2_trade)
       
        #return the trade status and updated inventory/gold status for both players
        trade['trade_time'] = trade_time
        return json.dumps(trade)

    else:
        #return cached inventory and gold state for each player along with fail reason
        cached_states = {}
        cached_states['player_1'] = working_trade.player_1_cache_state.to_dict()
        cached_states['player_2'] = working_trade.player_2_cache_state.to_dict()
        cached_states['fail_reason'] = fail_reason
        cached_states['trade_time'] = trade_time
        
        trade = working_trade.to_dict()
        player_1_trades = [construct_trade_dict(trade_id,
                                                trade['player_1']['player_id'],
                                                trade_time,
                                                i,
                                                trade['player_1']['gold_traded'],
                                                valid_trade,
                                                fail_reason) for i in trade['player_1']['items_traded']]
        player_2_trades = [construct_trade_dict(trade_id,
                                                trade['player_2']['player_id'],
                                                trade_time,
                                                i,
                                                trade['player_2']['gold_traded'],
                                                valid_trade,
                                                fail_reason) for i in trade['player_2']['items_traded']]
        
        #log the failed trade to kafka
        for player_1_trade in player_1_trades:
            log_to_kafka('events',player_1_trade)
        for player_2_trade in player_2_trades:
            log_to_kafka('events',player_2_trade)

        return json.dumps(cached_states)
```

The `create_player` route takes a PUT request containing a JSON object defining the player's desired username and class (see `data/test_player.json` for an example). If no username is specified, one it chosen at random. If a player class is defined as anything valid other than "random," the starting inventory is generated according to their selection (see `src/inventory_generation/generate_inventory.py`). If the class selection is not specified, then a random class is chosen with the corresponding inventory according to a specific class distribution in the game (see `src/generate_inventory.py`). The `create_player` route examines which player ids already exist and generates a new one. Once all of this has taken place, the player's inventory state is cached in Redis keyed under their `player_id`. An event is logged to Kafka for every item in their inventory. If successful, a message is returned to the client indicating the request was successful.

The `trade` route takes a POST request containing a JSON object defining the player's involved, their inventory states, amounts of gold they have, the items they are each trading, and the gold they are each trading (see `data/test_data.json` for an example). Core game logic is used to validate the trades in terms of verifying that each player has enough gold/items to trade and enough inventory space to execute the trade. The players' states included in the request are verified against the Redis cache in order to prevent spoofing of the data sent to the API. If the trade is successful, each of the items traded, and the new player states are logged as events to Kafka. The Redis cache is also updated with the new player states. The new player states are then returned to the client. Should the trade be unsuccessful, the details of the trade and the reason it failed are logged to Kafka. The cached inventory states are returned to the client along with the reason for the trade failure.

#### 1.1 Commands

The Flask server can be spun up with the command below. Make sure you have a separate SSH session or `tmux` pane open before running this command or you will be blocked from running anything else.

```bash
docker-compose exec mids env FLASK_APP=/w205/project-3-nsylva/app.py flask run --host 0.0.0.0
```

### 2. Keeping Track of Player States Using Redis

A core feature to our game is maintaining synchronization between the game client and our back end system. An imperative goal is ensuring the integrity of the game environment and that fishy behavior is prevented when possible and logged when not. The key component to this initiative is the Redis cache. A Redis cache is an in-memory key/value store. The keys in the Redis cache used for this pipeline is the `player_id` and the value is a JSON string representing the player's state including their username, items in their inventory, and the amount of gold that they have. 

The Python package `redis` allows for easy communication with a Redis cache. Usage of the cache for getting and setting player states can be observed in the `app.py` file in the root directory or within the `Trade` class definition inside the `src/Trade.py` file. A simple example of how getting and setting states works follows:

```python
def get_state(id):
    '''
    Merely a wrapper for reading from the Redis cache. 
    Returns a dict created from a string parsed as JSON.
    '''
    state = json.loads(redis_host.get(str(id)))
    return state
  
def set_state(id,state = {}):
    '''
    Sets a key to the specified dictionary object converted to JSON.
    Returns the set state.
    '''
    state_json = json.dumps(state)
    redis_host.mset({str(id):state_json})
    return state
```

#### 2.1 Commands

No commands are necessary to initialize the Redis cache beyond spinning up the containers as specified in section **0.1**.

### 3. Logging Events to Kafka

Individual player state and trade events are logged to a Kafka message queue to be processed with Spark Streaming. An individual player state or trade is broken up into the items that are contained within the event and sent to Kafka as a series of messages. Each message in the series contains a unique identifier for the event so that all messages can easily be aggregated on the query-side and exact player state and trade events can be replayed. All messages are published to a single Kafka topic called "events." 

#### 3.1 Commands

To create the Kafka topic, run the following command: 

```bash
docker-compose exec kafka kafka-topics --create --topic events --partitions 1 --replication-factor 1 --if-not-exists --zookeeper zookeeper:32181
```

If you want to see the events come into the queue as they are generated, in a separate ssh session or `tmux` pane (you will be blocked from executing other commands if you do not), execute the following command:

```bash
docker-compose exec mids kafkacat -C -b kafka:29092 -t events -o beginning
```

### 4. Landing Player State and Trade Data as it Occurs in HDFS using Kafka and Spark

Our events that come through the Kafka message queue need to be transformed slightly and have a schema applied before being landed in HDFS. All of these processes can be handled using Spark Streaming.  Because this project has two event types, we will spin up a Spark Streaming job for both event types, `trade` and `player_state`. 

Both applications read from the same Kafka topic, "events," filter the appropriate event type, define the event schema, and land the data at the appropriate location in HDFS as a parquet file (`/tmp/trades` and `/tmp/player_states`. The streaming window for the files is set to 30 seconds, meaning that all events that land in the Kafka queue are processed incrementally every 30 seconds. The length of this window is currently larger than necessary based on the load applied during benchmarking and trade simulation, but will allow some flexibility for larger loads in production.

The Spark job files, `write_trade_from_stream.py` and `write_player_state_from_stream.py` are located in the `src` directory.

#### 4.1 Commands

The Spark jobs need to be started in two separate SSH sessions or `tmux` panes from your primary sessio in order to avoid command-blocking. Run each of the following commands in its own session/pane:

```bash
# trade stream
docker-compose exec spark spark-submit /w205/project-3-nsylva/src/write_trade_from_stream.py
# player_state stream
docker-compose exec spark spark-submit /w205/project-3-nsylva/src/write_player_state_from_stream.py
```

There will be a log of log activity displayed in each of these sessions/panes. After its initialization, you'll be able to watch the jobs process each 30 second window of streaming.

After getting everything running, it is necessary to register the schemas for our two parquet tables in Hive. First, enter the Hive shell:

```bash
docker-compose exec cloudera hive
```

Once the Hive shell has loaded, execute the following two commands:

```bash
# player_state schema registration
create external table if not exists default.player_states (`Accept` string, `Accept-Encoding` string, `Connection` string, `Content-Length` string, `Content-Type` string, `Host` string, `User_Agent` string, `timestamp` string, `raw_event` string, `event_type` string, `state_id` string, `state_time` string, `player_id` string, `username` string, `player_class` string, `inventory_max_capacity` int, `inventory_current_capacity` int, `item_held_item_id ` int, `item_held_name` string, `item_held_level` int, `item_held_value` int, `item_held_quantity` int, `gold` int) stored as parquet location '/tmp/player_states'  tblproperties ("parquet.compress"="SNAPPY");

# trades schema registration
create external table if not exists default.trades (`Accept` string, `Accept-Encoding` string, `Connection` string, `Content-Length` string, `Content-Type` string, `Host` string, `User_Agent` string, `timestamp` string, `raw_event` string, `event_type` string, `trade_time` string, `trade_id` string, `valid_trade` string, `fail_reason` string, `player_id` string, `item_traded_item_id` string, `item_traded_name` string, `item_traded_level` int, `item_traded_value` int, `item_traded_quantity` int, `gold_traded` int) stored as parquet location '/tmp/trades'  tblproperties ("parquet.compress"="SNAPPY");
```

Use Ctrl-D to exit the Hive shell.

### 5. Simulating Player Creation and Trade Activity with Apache Bench and Python

In order to simulate trades, we need to have players that can execute the trade. Because our game is still pre-alpha testing, the only way we can do that is by generating them randomly. Apache Bench, `ab` provides a way for us send many requests to a given API route. Conveniently, we can also seed each request with an identical JSON file. The JSON file used for this process is saved here: `data/test_player.json`. All this file contains is a single JSON key/value pair indicating that a player of random class is to be generated. Because there is no username key, the Trade Engine code will handle assigning a random username.

```json
{
	"player_class" : "random"
}
```

Once we have a set of players created randomly through Apache Bench, we can simulate simple trading between them. A simple trade is a one for one item swap with no gold exchange and no consideration of item value. This process will allow us to test the system and create data for us to analyze. Note that this is not intended to reflect normal user behavior. Because Apache Bench does not allow for assigning different content for each request, it is easier to write a Python script to submit a bunch of requests to the `/trade` route. The code also allows for the randomization of players and items traded. The script for generating the trades is located at `/src/trade_generation.py` and is omitted from this narrative for brevity.

#### 5.1 Commands

To generate 1,000 random players using Apache Bench, run the following command:

```bash
docker-compose exec mids ab -u /w205/project-3-nsylva/data/test_player.json -T application/json -n 1000 http://localhost:5000/create_player
```

After generating the players, 10,000 trades can be simulated with the command below. Note, this runs on one thread so it may be helpful to run it in a separate SSH session or `tmux` pane. Additional commands will be blocked while running:

```bash
docker-compose exec mids python /w205/project-3-nsylva/src/trade_simulation.py
```

### 6. Querying the Data with Presto to Answer Business Questions

Before querying any data, it is important to double check that we indeed have our simulated data stored in HDFS. We can take a look at our HDFS partitions with the following two commands.

```bash
# check trades
docker-compose exec cloudera hadoop fs -ls /tmp/trades

# check player_states
docker-compose exec cloudera hadoop fs -ls /tmp/player_states
```

Next, we'll fire up Presto to check our tables and run some queries:

```bash
docker-compose exec presto presto --server presto:8080 --catalog hive --schema default
```

Check that the tables exist:

```
presto:default> show tables;
```

Verify the schemas for each table:

```
presto:default> describe trades;
presto:default> describe player_states;
```

Now that we have confirmed that our tables exist and have appropriate schemas we can start answering business questions. **Note:** If you run these same queries, some of your answers will differ due to the random nature of player and trade generation.

#### Question 1: How many trades occurred?

**Query:** 

```sql
select count(distinct trade_id) from trades;
```

**Result:** 

10,000 (as expected)

#### Question 2: Which item is traded most often?

**Query:**

```sql
select item_traded_item_id, item_traded_name, count(*) as num_traded from trades group by item_traded_item_id, item_traded_name order by num_traded desc;
```

**Result:** 

Item with `item_id` = 5, Food Package, was traded 2,019 times.

#### Question 3: Which player has the most diverse inventory (greatest number of different items) at any given time?

**Query:**

```sql
select player_id, username, state_id, state_time, count(distinct item_held_item_id) as num_uniq_items from player_states group by state_id, player_id, username, state_time order by num_uniq_items desc limit 1;
```

**Result:**

Player with `player_id` = 917, Kedasi,  had 12 different items at 12/10/2019, 23:31:11.954014.

#### Question 4: Which player has the greatest gold value in terms of items in their inventory at any given time?

**Query:**

```sql
select player_id, username, state_id, state_time, gold, sum(item_held_value * item_held_quantity) as cum_item_value from player_states group by state_id, player_id, username, state_time, gold order by cum_item_value desc limit 1;
```

**Result:**

Player with `player_id` = 376, Lafbert had a total of 159,251,100 gold worth of items at 12/10/2019, 23:27:21.616499. He also had an additional 10,000,000 gold in his account.

