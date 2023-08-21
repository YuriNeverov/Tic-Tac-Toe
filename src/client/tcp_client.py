import socket

HOST = "127.0.0.1"
PORT = 8080

cin = input("? ")
while cin != "quit":
  try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
      s.connect((HOST, PORT))
      s.settimeout(4)
      s.sendall(bytes(cin, encoding="utf-8"))
      data = s.recv(1024)
      print(f"Received {data!r}")
  except TimeoutError as e:
    print("Timed Out")
  cin = input("? '")
