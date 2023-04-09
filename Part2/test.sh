#create broker
# curl -X POST  -H 'Content-Type: application/json' http://127.0.0.1:5000/broker/register

# create topic
# curl -X POST -d '{"name": "T-2", "partitions":7}' -H 'Content-Type: application/json' http://127.0.0.1:5000/topics
# curl -X POST -d '{"name": "T-1", "partitions":7}' -H 'Content-Type: application/json' http://127.0.0.1:5000/topics
# curl -X POST -d '{"name": "T-11", "partitions":7}' -H 'Content-Type: application/json' http://127.0.0.1:5000/topics

#create broker manager
# curl -X POST -d '{"ip": "rbm2", "managertype":"0"}' -H 'Content-Type: application/json' http://127.0.0.1:5000/managers/add


#create producer and consumer
# curl -X POST -d '{"topic": "T-11"}' -H 'Content-Type: application/json' http://127.0.0.1:5000/producer/register
# curl -X POST -d '{"topic": "T-11"}' -H 'Content-Type: application/json' http://127.0.0.1:5000/consumer/register

#produce two messages
curl -X POST -d '{"topic": "T-11","producer_id":1000011, "message": "hello into partition 1 message 4", "partition":1}' -H 'Content-Type: application/json' http://127.0.0.1:5000/producer/produce
# curl -X POST -d '{"topic": "T-11","producer_id":1000031, "message": "hello into partition 1 message 3", "partition":0}' -H 'Content-Type: application/json' http://127.0.0.1:5000/producer/produce

# curl -X POST -d '{"topic": "producer_signup","producer_id":10000000000001, "message": "hello2"}' -H 'Content-Type: application/json' http://127.0.0.1:5000/producer/produce


# #check size to be 2
# curl -X GET  -d '{"topic": "T-11","consumer_id":2000010}' -H 'Content-Type: application/json' http://127.0.0.1:8080/size

# first message to be retrieved

# curl -X GET  -d '{"topic": "T-11","consumer_id":2000010, "partition":1}' -H 'Content-Type: application/json' http://127.0.0.1:8080/consumer/consume

# #queue size should change to 1
# curl -X GET  -d '{"topic": "producer_signup","consumer_id":10000000000000}' -H 'Content-Type: application/json' http://127.0.0.1:5000/size

# Retrieve Second Message
# curl -X GET  -d '{"topic": "producer_signup","consumer_id":10000000000000}' -H 'Content-Type: application/json' http://127.0.0.1:5000/consumer/consume

# Check size should be zero
# curl -X GET  -d '{"topic": "producer_signup","consumer_id":10000000000000}' -H 'Content-Type: application/json' http://127.0.0.1:5000/size

# Check Broker Partition Assignment Register
# curl -X POST -d '{"name": "producer_signup", "partition_id": 1}' -H 'Content-Type: application/json' http://127.0.0.1:5001/partitions

# curl -X POST -H 'Content-Type: application/json' http://127.0.0.1:5000/broker/register


# curl -X POST  -d '{"broker_id":1}' -H 'Content-Type: application/json' http://127.0.0.1:5000/heartbeat
