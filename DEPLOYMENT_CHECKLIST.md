# Security Hardening - Quick Deployment Checklist

## ✅ Already Implemented (Django)

### Django Settings Updates (myuganda/settings.py)
- [x] Added Content-Security-Policy (CSP) configuration
- [x] Increased SECURE_HSTS_SECONDS to 31536000 (1 year)
- [x] Changed X_FRAME_OPTIONS from 'DENY' to 'SAMEORIGIN'
- [x] Added SESSION_COOKIE_SAMESITE = 'Strict'
- [x] All CSP directives configured (script-src, style-src, img-src, etc.)

### Middleware Implementation
- [x] Created `myuganda/middleware.py` with:
  - HTTPMethodSecurityMiddleware (blocks PUT, DELETE, TRACE, CONNECT)
  - SecurityHeadersMiddleware (adds Permissions-Policy, X-XSS-Protection)
- [x] Added middleware to MIDDLEWARE list in settings.py

---

## 🔄 To Deploy on Production Server

### On Your Production Server (172.66.172.174)

#### Step 1: Backup Current Configuration
```bash
sudo cp /etc/apache2/apache2.conf /etc/apache2/apache2.conf.backup
sudo cp /etc/apache2/sites-available/africanaai-info-ssl.conf /etc/apache2/sites-available/africanaai-info-ssl.conf.backup
```

#### Step 2: Enable Required Apache Modules
```bash
sudo a2enmod rewrite
sudo a2enmod headers
sudo a2enmod ssl
sudo systemctl restart apache2
```

#### Step 3: Create Security Headers Configuration File
```bash
sudo nano /etc/apache2/conf-available/security-headers.conf
```

**Copy & paste content from**: `APACHE_SECURITY_HARDENING.conf` (lines 17-52)

**Save**: Press Ctrl+X, then Y, then Enter

#### Step 4: Enable the Security Headers Configuration
```bash
sudo a2enconf security-headers
```

#### Step 5: Update SSL Configuration
```bash
sudo nano /etc/apache2/mods-available/ssl.conf
```

**Find the section** (usually line ~85):
```apache
#SSLProtocol all
#SSLCipherSuite HIGH:!aNULL:!MD5
```

**Replace with** (from APACHE_SECURITY_HARDENING.conf, lines 57-67):
```apache
SSLProtocol all -SSLv2 -SSLv3 -TLSv1 -TLSv1_1
SSLCipherSuite 'EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH'
SSLHonorCipherOrder on
SSLUseStapling on
SSLStaplingCache "shmcb:logs/stapling-cache(150000)"
```

**Save**: Press Ctrl+X, then Y, then Enter

#### Step 6: Test Apache Configuration
```bash
sudo apache2ctl configtest
```

**Expected Output**: `Syntax OK`

If you get errors, double-check the syntax and try again.

#### Step 7: Gracefully Restart Apache (Zero Downtime)
```bash
sudo apache2ctl graceful
```

---

## ✅ Verification (After Deployment)

### Test 1: Check Security Headers
```bash
curl -I https://africanaai.info
```

**Look for**:
- ✅ `Strict-Transport-Security: max-age=31536000`
- ✅ `X-Content-Type-Options: nosniff`
- ✅ `X-Frame-Options: SAMEORIGIN`
- ✅ `Content-Security-Policy: default-src 'self'...`
- ✅ `Referrer-Policy: no-referrer-when-downgrade`

### Test 2: Check TLS Configuration
```bash
# This should work (TLS 1.2 allowed)
openssl s_client -connect africanaai.info:443 -tls1_2
# Expected: Successfully connected

# This should fail (TLS 1.0 disabled)
openssl s_client -connect africanaai.info:443 -tls1
# Expected: Connection refused or error
```

### Test 3: Check HTTP Method Restrictions
```bash
# PUT should be blocked
curl -X PUT https://africanaai.info/
# Expected: "405 Method Not Allowed"

# GET should work
curl -X GET https://africanaai.info/
# Expected: "200 OK" or your normal response
```

### Test 4: Full SSL Report
Visit: https://www.ssllabs.com/ssltest/analyze.html?d=africanaai.info

**Expected Grade**: A+ (was B/C before)

---

## 🔍 Monitoring After Deployment

### Check Apache Logs
```bash
# Real-time errors
sudo tail -f /var/log/apache2/error.log

# Monitor blocked requests
sudo tail -f /var/log/apache2/access.log | grep "405"

# Check for CSP violations (if enabled logging)
sudo grep "CSP" /var/log/apache2/error.log
```

### Common Issues & Fixes

**Issue**: "Syntax OK" passes but Apache won't restart
```bash
# Check detailed error
sudo apache2ctl -S

# Look for conflicting configurations
# Disable conflicting modules:
sudo a2dismod mpm_prefork  # if using mpm_event
```

**Issue**: CSP is too strict, blocking legitimate content
```bash
# Solution: Update CSP policy in /etc/apache2/conf-available/security-headers.conf
# Add domains that need access to: script-src, style-src, font-src, etc.
# Restart: sudo apache2ctl graceful
```

**Issue**: SSL certificate issues after TLS update
```bash
# Verify certificate validity
openssl x509 -in /etc/letsencrypt/live/africanaai.info/fullchain.pem -text -noout

# If using Let's Encrypt, auto-renewal should handle it:
sudo systemctl status certbot.timer
```

**Issue**: Large file uploads fail with `413 Payload Too Large`
```bash
# Check if Apache is rejecting uploads before Django sees them
sudo grep -R "LimitRequestBody" /etc/apache2
# Or if using Nginx in front of Apache:
grep -R "client_max_body_size" /etc/nginx
```

**Fix**: Raise the proxy/web-server upload limit
```apache
# Apache
LimitRequestBody 89128960

# Nginx
client_max_body_size 85M;
```

Restart the web server after changing the limit:
```bash
sudo apache2ctl graceful
sudo systemctl reload nginx
```

---

## 📋 Before & After Comparison

### BEFORE (Vulnerable)
```
❌ No CSP - XSS attacks possible
❌ TLS 1.0/1.1 allowed - POODLE attacks possible
❌ PUT/DELETE allowed - File upload/deletion attacks possible
❌ No X-Frame-Options - Clickjacking possible
❌ Weak cipher suites - Weak encryption
❌ Grade: C or B on SSL Labs
```

### AFTER (Hardened)
```
✅ CSP enforced - XSS attacks blocked
✅ TLS 1.2+ only - POODLE protection
✅ HTTP methods restricted - File operations blocked
✅ X-Frame-Options: SAMEORIGIN - Clickjacking blocked
✅ Modern cipher suites - Strong encryption
✅ Grade: A+ on SSL Labs
```

---

## 🚀 Rollback Plan (If Needed)

If something breaks:

```bash
# Disable the new security headers config
sudo a2disconf security-headers

# Restore SSL configuration
sudo cp /etc/apache2/mods-available/ssl.conf.backup /etc/apache2/mods-available/ssl.conf

# Restart Apache
sudo apache2ctl graceful

# Fix issues, then re-enable:
# sudo a2enconf security-headers
# sudo apache2ctl graceful
```

---

## 📞 Support Resources

- **Apache Documentation**: https://httpd.apache.org/docs/
- **Mozilla SSL Configuration**: https://wiki.mozilla.org/Security/Server_Side_TLS
- **OWASP CSP**: https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html
- **Let's Encrypt**: https://letsencrypt.org/docs/

---

## Estimated Timeline

| Task | Time | Difficulty |
|------|------|-----------|
| Django settings update | 5 min | Easy |
| Create middleware | 10 min | Easy |
| Backup Apache config | 5 min | Easy |
| Enable modules | 2 min | Easy |
| Add security headers config | 10 min | Easy |
| Update SSL config | 10 min | Medium |
| Test syntax & restart | 5 min | Easy |
| Verify all tests pass | 10 min | Easy |
| **Total** | **57 min** | **Mostly Easy** |

---

## Final Checklist

- [ ] Django settings.py deployed to production
- [ ] Middleware enabled and tested locally
- [ ] Apache backup created
- [ ] Required modules enabled
- [ ] Security headers config file created
- [ ] SSL configuration hardened
- [ ] Apache syntax verified (configtest)
- [ ] Apache gracefully restarted
- [ ] All 4 verification tests passing
- [ ] SSL Labs report shows A+ grade
- [ ] Logs reviewed for errors
- [ ] Team notified of changes

---

**Status**: Ready for deployment ✅

**Last Updated**: June 4, 2026
**Version**: 1.0
