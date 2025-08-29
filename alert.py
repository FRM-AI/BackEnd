import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_alert(subject, signals, to_email):
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # dùng 465 nếu sử dụng SSL
    smtp_user = "nhghung22@clc.fitus.edu.vn"  # địa chỉ email của bạn
    smtp_password = "qlisyqsalzagzsmn"  # mật khẩu ứng dụng (nếu bật xác thực 2 bước)

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject

    body = "\n".join(signals)
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Khởi tạo kết nối bảo mật
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()
        print(f"Alert sent successfully to {to_email}")
    except Exception as e:
        print(f"Failed to send alert: {e}")