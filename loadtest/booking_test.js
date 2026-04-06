import http from 'k6/http'
import { check, sleep } from 'k6'

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '60s', target: 50 },
    { duration: '30s', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed:   ['rate<0.05'],
  },
}

const EU_LB   = __ENV.EU_LB   || 'http://35.240.110.205'
const US_LB   = __ENV.US_LB   || 'http://34.26.94.36'
const APAC_LB = __ENV.APAC_LB || 'http://34.126.131.195'

function getToken(baseUrl) {
  const res = http.post(
    `${baseUrl}/auth/login`,
    JSON.stringify({ email: 'driver@trafficbook.com', password: 'Driver123!' }),
    { headers: { 'Content-Type': 'application/json' } }
  )
  return JSON.parse(res.body).access_token
}

export default function () {
  const lb = [EU_LB, US_LB, APAC_LB][Math.floor(Math.random() * 3)]
  const token = getToken(lb)

  const routes = [
    { origin: 'Dublin, Ireland',    destination: 'Cork, Ireland' },
    { origin: 'New York, USA',      destination: 'Boston, USA' },
    { origin: 'Singapore',          destination: 'Kuala Lumpur, Malaysia' },
  ]
  const route = routes[Math.floor(Math.random() * routes.length)]

  const res = http.post(
    `${lb}/journeys`,
    JSON.stringify({
      origin:      route.origin,
      destination: route.destination,
      start_time:  '2026-06-01T09:00:00',
    }),
    {
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${token}`,
      },
    }
  )

  check(res, {
    'status 200 or 201':      (r) => r.status === 200 || r.status === 201,
    'response time < 500ms':  (r) => r.timings.duration < 500,
  })

  sleep(1)
}
