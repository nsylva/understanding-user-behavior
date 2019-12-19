#!/usr/bin/env python
"""Extract events from kafka and write them to hdfs
"""
import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, from_json
from pyspark.sql.types import StructType, StructField, StringType, LongType


def trade_event_schema():
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
        StructField("trade_time", StringType(),True),
        StructField("trade_id", StringType(),True),
        StructField("valid_trade", StringType(),True),
        StructField("fail_reason", StringType(),True),
        StructField("player_id", StringType(),True),
        StructField("item_traded_item_id",StringType(),True),
        StructField("item_traded_name",StringType(),True),
        StructField("item_traded_level",LongType(), True),
        StructField("item_traded_value",LongType(), True),
        StructField("item_traded_quantity",LongType(), True),
        StructField("gold_traded", LongType(),True)
    ])


@udf('boolean')
def is_trade(event_as_json):
    """udf for filtering events
    """
    event = json.loads(event_as_json)
    if event['event_type'] == 'trade':
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

    trades = raw_events.filter(is_trade(raw_events.value.cast('string'))) \
        .select(raw_events.value.cast('string').alias('raw_event'),
                raw_events.timestamp.cast('string'),
                from_json(raw_events.value.cast('string'),
                          trade_event_schema()).alias('json')) \
        .select('raw_event', 'timestamp', 'json.*')

    sink = trades \
        .writeStream \
        .format("parquet") \
        .option("checkpointLocation", "/tmp/checkpoints_for_trades") \
        .option("path", "/tmp/trades") \
        .trigger(processingTime="30 seconds") \
        .start()

    sink.awaitTermination()


if __name__ == "__main__":
    main()