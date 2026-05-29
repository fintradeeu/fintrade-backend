import smtplib

host = "smtp.hostinger.com"
user = "info@thefintrade.com"
pwd = "zc8983qzc67eetce"

print("--- Testing Port 465 SSL ---")
try:
    with smtplib.SMTP_SSL(host, 465) as server:
        server.set_debuglevel(1)
        server.login(user, pwd)
        print("Success 465 SSL!")
except Exception as e:
    print("Failed 465 SSL:", e)

print("\n--- Testing Port 587 STARTTLS ---")
try:
    with smtplib.SMTP(host, 587) as server:
        server.set_debuglevel(1)
        server.starttls()
        server.login(user, pwd)
        print("Success 587 STARTTLS!")
except Exception as e:
    print("Failed 587 STARTTLS:", e)
