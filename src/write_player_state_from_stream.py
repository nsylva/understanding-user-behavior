#!/usr/bin/env python
"""Extract events from kafka and write them to hdfs
"""
import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, from_json
from pyspark.sql.types import StructType, StructField, StringType, LongType


def player_state_event_schema():
    """
    root
    |-- Accept: string (nullable = true)
    |-- Host: string (nullable = true)
    |-- User-Agent: string (nullable = true)
    |-- event_type: string (nullable = true)
    |-- timestamp: string (nullable = true)
    """
    return StructType([
        StructField("Accept", StringType(), True),
        StructField("Accept-Encoding", StringType(), True),
        StructField("Connection", StringType(), True),
        StructField("Content-Length", StringType(), True),
        StructField("Content-Type", StringType(), True),
        StructField("Host", StringType(), True),
        StructField("User-Agent", StringType(), True),
        StructField("event_type", StringType(), True),
        StructField("state_id", StringType(), True),
        StructField("state_time", StringType(), True),
        StructField("player_id", StringType(), True),
        StructField("username", StringType(), True),
        StructField("player_class", StringType(), True),
        StructField("inventory_max_capacity",LongType(), True),
        StructField("inventory_current_capacity",LongType(), True),
        StructField("item_held_item_id", LongType(), True),
        StructField("item_held_name",StringType(),True),
        StructField("item_held_level",LongType(), True),
        StructField("item_held_value",LongType(), True),
        StructField("item_held_quantity",LongType(), True),
        StructField("gold", LongType(), True)
    ])


@udf('boolean')
def is_player_state(event_as_json):
    """udf for filtering events
    """
    event = json.loads(event_as_json)
    if event['event_type'] == 'player_state':
        return True
    return False

def main():
    """main
    """
    spark = SparkSession \
        .builder \
        .appName("ExtractEventsJob") \
        .getOrCreate()

    raw_events = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:29092") \
        .option("subscribe", "events") \
        .load()

    player_states = raw_events.filter(is_player_state(raw_events.value.cast('string'))) \
        .select(raw_events.value.cast('string').alias('raw_event'),
                raw_events.timestamp.cast('string'),
                from_json(raw_events.value.cast('string'),
                          player_state_event_schema()).alias('json')) \
        .select('raw_event', 'timestamp', 'json.*')

    sink = player_states \
        .writeStream \
        .format("parquet") \
        .option("checkpointLocation", "/tmp/checkpoints_for_player_states") \
        .option("path", "/tmp/player_states") \
        .trigger(processingTime="30 seconds") \
        .start()

    sink.awaitTermination()


if __name__ == "__main__":
    main()