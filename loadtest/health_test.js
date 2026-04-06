import http from 'k6/http'
import { check } from 'k6'

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(99)<100'],
  },
}

const LBS = [
  __ENV.EU_LB   || 'http://35.240.110.205',
  __ENV.US_LB   || 'http://34.26.94.36',
  __ENV.APAC_LB || 'http://34.126.131.195',
]

export default function () {
  LBS.forEach(lb => {
    const res = http.get(`${lb}/health`)
    check(res, {
      'healthy': (r) => r.status === 200,
    })
  })
}
