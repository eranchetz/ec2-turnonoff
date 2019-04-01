import logging
import boto3
import os
from queue import Queue
from threading import Thread
from datetime import datetime

version = '1.0'


# Todo: performance tests, and check that pagination actually works

###
# Logic:
# 1. Turn On instances with "TurnOn" tag.
# 2. Do not turn on instances in weekend if environment variable 'workweek_tag' is exist.
# 3. If environment tag 'workweek_tag' equal Sunday, instances will not turned on on Friday and Saturday.
#   --- If tag equal Monday, instances will not turned on on Saturday and Sunday. 
# 4. Turn Off instances with "TurnOff" tag.
# 5. Supports pagination and multithreading.
###


class Aws:
    def __init__(self, region='us-east-1'):
        self.region = region
        self.session = boto3.Session()

    def get_regions(self):
        return [region['RegionName'] for region in
                self.session.client('ec2').describe_regions()['Regions']]

    def get_ec2_instances(self, region, queue):
        instances = {}

        response = self.session.client('ec2', region_name=region).describe_instances()
        while response:
            # default values, will be overridden if actually exist
            if response['Reservations']:
                for reservations in response['Reservations']:
                    instance_name = ''
                    turn_off = ''
                    turn_on = ''
                    if reservations['Instances']:
                        for instance in reservations['Instances']:
                            if 'Tags' in instance:
                                for name in instance['Tags']:
                                    if name['Key'] == 'Name':
                                        instance_name = name['Value']
                                    if name['Key'] == 'TurnOn':
                                        turn_on = name['Value']
                                    if name['Key'] == 'TurnOff':
                                        turn_off = name['Value']
                            data = {'name': instance_name, 'id': instance['InstanceId'],
                                    'state': instance['State']['Name'], 'turn_on': turn_on,
                                    'turn_off': turn_off}
                            if region in instances:
                                instances[region].append(data)
                            else:
                                instances[region] = [data]
            response = self.session.client('ec2', region_name=region).describe_instances(
                NextToken=response['NextToken']) if 'NextToken' in response else None
        queue.put(instances)
        queue.task_done()
        return instances

    def ec2_turn_off(self, aws_region_turnon: str, instances_list: list):
        response = self.session.client('ec2', region_name=aws_region_turnon).stop_instances(InstanceIds=instances_list)
        return response

    def ec2_turn_on(self, aws_region_turnoff: str, instances_list: list):
        response = self.session.client('ec2', region_name=aws_region_turnoff).start_instances(
            InstanceIds=instances_list)
        return response


def workweek_start_tag():
    # To disable turn on servers on weekend, Please set environment variable of 'workweek_tag'
    if 'workweek_tag' in os.environ:
        return str(os.environ['workweek_tag'])
    else:
        return ''


def lambda_handler(event, context):
    # Variables
    aws = Aws('us-east-1')
    current_time = datetime.now().strftime('%H:%M')
    workweek_start = workweek_start_tag()
    today = datetime.now().strftime('%A')

    # Logging handling
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    regions_list = aws.get_regions()
    q = Queue()
    threads = []

    for r in regions_list:
        t = Thread(target=aws.get_ec2_instances, args=(r, q), daemon=True)
        turn_on_list = []
        turn_off_list = []
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    q.join()
    results = {}
    while q.qsize():
        q_item = q.get()
        if q_item:
            results = {**results, **q_item}

    for aws_region, data in results.items():
        for item in data:
            if 'turn_on' in item and item['turn_on'] == current_time:
                turn_on_list.append(item['id'])
            if 'turn_off' in item and item['turn_off'] == current_time:
                turn_off_list.append(item['id'])

        if turn_on_list:
            if workweek_start == "Sunday" and (today == "Friday" or today == "Saturday"):
                continue
            elif workweek_start == "Monday" and (today == "Saturday" or today == "Sunday"):
                continue
            else:
                logger.info(f'in region {aws_region}, going to turn on {turn_on_list}')
                try:
                    aws.ec2_turn_on(aws_region, turn_on_list)
                except Exception as e:
                    logger.error(str(e))

        if turn_off_list:
            logger.info(f'in region {aws_region}, going to turn off {turn_off_list}')
            try:
                aws.ec2_turn_off(aws_region, turn_off_list)
            except Exception as e:
                logger.error(str(e))
    return 'detailed log in Cloudwatch'
