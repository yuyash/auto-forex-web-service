# Nginx Rate Limiting Configuration

## Overview

This document describes the rate limiting implementation in the Auto Forex Trader. Rate limiting protects the application from abuse, DDoS attacks, and excessive API usage.

## Implementation

### Configuration Location

Rate limiting is configured in:

- **Main config**: `nginx/nginx.conf` - Defines rate limit zones and status code
- **Server configs**: `nginx/conf.d/*.conf` - Applies rate limits to specific endpoints

### Rate Limit Zones

Two zones are defined in `nginx.conf`:

```nginx
# General API endpoints: 100 requests per minute per IP
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;

# Authentication/Admin endpoints: 5 requests per minute per IP
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

# Return 429 Too Many Requests when limit exceeded
limit_req_status 429;
```

### Endpoint Configuration

| Endpoint          | Zone        | Rate    | Burst | Description           |
| ----------------- | ----------- | ------- | ----- | --------------------- |
| `/api/*`          | api_limit   | 100/min | 20    | General API endpoints |
| `/api/admin/*`    | login_limit | 5/min   | 5     | Admin operations      |
| `/api/auth/login` | login_limit | 5/min   | 3     | Login endpoint        |

## How It Works

### Rate Limiting Algorithm

Nginx uses the **leaky bucket** algorithm:

1. Each IP address has a "bucket" that fills with requests
2. The bucket "leaks" at the configured rate (e.g., 100 req/min)
3. Burst allows temporary overflow before rejecting requests
4. Requests exceeding rate + burst are rejected with 429 status

### Example Scenarios

#### Scenario 1: Normal Usage

```
IP: 192.168.1.100
Endpoint: /api/accounts/
Rate: 100 req/min, Burst: 20

Requests 1-100: ✓ Accepted (within rate)
Requests 101-120: ✓ Accepted (within burst)
Requests 121+: ✗ Rejected with 429
```

#### Scenario 2: Login Attempts

```
IP: 192.168.1.100
Endpoint: /api/auth/login
Rate: 5 req/min, Burst: 3

Requests 1-5: ✓ Accepted (within rate)
Requests 6-8: ✓ Accepted (within burst)
Requests 9+: ✗ Rejected with 429
```

## Response Format

When rate limit is exceeded, nginx returns:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: text/html
Content-Length: 169

<html>
<head><title>429 Too Many Requests</title></head>
<body>
<center><h1>429 Too Many Requests</h1></center>
<hr><center>nginx</center>
</body>
</html>
```

## Testing

### Manual Testing

Test API rate limit (100 req/min):

```bash
# Send 125 requests rapidly
for i in {1..125}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/accounts/
done

# Expected: First 120 return 200, remaining return 429
```

Test login rate limit (5 req/min):

```bash
# Send 10 login requests rapidly
for i in {1..10}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"test"}'
done

# Expected: First 8 return 200/401, remaining return 429
```

### Automated Testing

Use tools like Apache Bench or wrk:

```bash
# Test with Apache Bench
ab -n 200 -c 10 http://localhost/api/accounts/

# Test with wrk
wrk -t4 -c100 -d30s http://localhost/api/accounts/
```

## Monitoring

### Access Logs

Rate limit events are logged in nginx access logs:

```bash
# View rate-limited requests
docker-compose logs nginx | grep "429"

# Or directly from log file
tail -f /var/log/nginx/access.log | grep "429"
```

Log format includes:

- IP address
- Timestamp
- Request path
- Status code (429)
- Response time

### Metrics

Monitor rate limiting effectiveness:

```bash
# Count 429 responses in last hour
docker-compose exec nginx sh -c \
  "grep '429' /var/log/nginx/access.log | grep $(date +%d/%b/%Y:%H) | wc -l"

# Top IPs being rate limited
docker-compose exec nginx sh -c \
  "grep '429' /var/log/nginx/access.log | awk '{print \$1}' | sort | uniq -c | sort -rn | head -10"
```

## Configuration Tuning

### Adjusting Rate Limits

To modify rate limits, edit `nginx/nginx.conf`:

```nginx
# Increase API rate to 200 req/min
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=200r/m;

# Decrease login rate to 3 req/min
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=3r/m;
```

Then reload nginx:

```bash
docker-compose exec nginx nginx -s reload
```

### Adjusting Burst

To modify burst limits, edit server configs in `nginx/conf.d/*.conf`:

```nginx
# Increase API burst to 50
location /api/ {
    limit_req zone=api_limit burst=50 nodelay;
    # ...
}
```

### Memory Allocation

Each zone allocates memory for tracking IPs:

- 10MB = ~160,000 IP addresses
- Increase if needed: `zone=api_limit:20m`

## Best Practices

1. **Monitor regularly**: Check logs for 429 responses
2. **Adjust as needed**: Tune rates based on legitimate usage patterns
3. **Whitelist if necessary**: Consider IP whitelisting for trusted sources
4. **Document changes**: Update this file when modifying rate limits
5. **Test after changes**: Verify configuration with `nginx -t`

## Troubleshooting

### Issue: Legitimate users getting 429

**Solution**: Increase rate or burst limits

```nginx
# Increase rate
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=200r/m;

# Or increase burst
limit_req zone=api_limit burst=50 nodelay;
```

### Issue: Rate limiting not working

**Checklist**:

1. Verify `limit_req_status 429;` is set in `nginx.conf`
2. Check `limit_req` directive is present in location blocks
3. Reload nginx: `docker-compose exec nginx nginx -s reload`
4. Check nginx error logs: `docker-compose logs nginx`

### Issue: Need to whitelist specific IPs

**Solution**: Use geo module or map directive

```nginx
# In nginx.conf http block
geo $limit {
    default 1;
    10.0.0.0/8 0;      # Internal network
    192.168.1.100 0;   # Trusted IP
}

map $limit $limit_key {
    0 "";
    1 $binary_remote_addr;
}

limit_req_zone $limit_key zone=api_limit:10m rate=100r/m;
```

## Security Considerations

1. **DDoS Protection**: Rate limiting provides basic DDoS protection
2. **Brute Force Prevention**: Login rate limiting prevents brute force attacks
3. **Resource Protection**: Prevents API abuse and resource exhaustion
4. **Monitoring Required**: Rate limiting alone is not sufficient - monitor logs
5. **Layer 7 Protection**: Consider additional WAF for advanced threats

## Compliance

This implementation satisfies:

- **Requirement 35.2**: "WHEN request rate from a single IP address exceeds 100 requests per minute, THE Nginx Server SHALL apply rate limiting"
- Returns HTTP 429 status code as required
- Logs all rate-limited requests for audit purposes

## References

- [Nginx Rate Limiting Documentation](http://nginx.org/en/docs/http/ngx_http_limit_req_module.html)
- [Nginx Rate Limiting Guide](https://www.nginx.com/blog/rate-limiting-nginx/)
- [RFC 6585 - HTTP Status Code 429](https://tools.ietf.org/html/rfc6585#section-4)
