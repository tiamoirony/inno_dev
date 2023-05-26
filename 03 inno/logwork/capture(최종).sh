#!/bin/bash

capture=0

while [ $capture -le 6 ]
do  
    curl -X GET http://localhost:8080/device/status/get/capture/
    echo '=============='
    echo '====capture==='
    echo '--------------'


    sleep 600
    echo '=============='
    echo '===Sleeping==='
    echo '--------------'
   ((capture++))

done
