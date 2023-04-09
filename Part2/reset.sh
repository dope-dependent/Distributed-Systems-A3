docker stop distributed-systems-a3-wmd1-1
docker stop distributed-systems-a3-rmd1-1
docker stop distributed-systems-a3-rmd2-1
docker stop distributed-systems-a3-db1-1
docker stop distributed-systems-a3-db2-1
docker stop distributed-systems-a3-db3-1


docker rm distributed-systems-a3-db1-1
docker rm distributed-systems-a3-db2-1
docker rm distributed-systems-a3-db3-1
docker rm distributed-systems-a3-wmd1-1
docker rm distributed-systems-a3-rmd1-1
docker rm distributed-systems-a3-rmd2-1




docker volume rm distributed-systems-a3_db1 
docker volume rm distributed-systems-a3_db2
docker volume rm distributed-systems-a3_db3
docker volume rm distributed-systems-a3_rmd1
docker volume rm distributed-systems-a3_rmd2
docker volume rm distributed-systems-a3_wmd1
