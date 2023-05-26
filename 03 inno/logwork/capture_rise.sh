#!/bin/bash

# 현재 시간 가져오기
current_hour=$(date +%H)
current_minute=$(date +%M)

# 시작 시간 설정
start_hour=19
start_minute=20

# 종료 시간 설정
end_hour=20
end_minute=20




# 시작 시간과 현재 시간 비교
if [[ ${current_hour#0} -gt ${start_hour#0} || (${current_hour#0} -eq ${start_hour#0} && $current_minute -ge $start_minute) ]]; then
  # 종료 시간과 현재 시간 비교
  if [[ ${current_hour#0} -lt ${end_hour#0} || (${current_hour#0} -eq ${end_hour#0} && $current_minute -le $end_minute) ]]; then
    # 10분마다 실행
    while [[ ${current_hour#0} -lt ${end_hour#0} || (${current_hour#0} -eq ${end_hour#0} && $current_minute -le $end_minute) ]]; do
      # 명령 실행
      curl -X GET http://localhost:8080/device/status/get/capture/

      # 10분 대기
      sleep 600

      # 현재 시간 갱신
      current_hour=$(date +%H)         
      current_minute=$(date +%M)
    done
  fi
fi