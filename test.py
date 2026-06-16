import urllib.request, json, urllib.error

def run_test():
    req = urllib.request.Request('http://127.0.0.1:8000/api/auth/login/', data=json.dumps({'email': 'attendee1', 'password': 'password123'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        res = urllib.request.urlopen(req)
        print(res.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(e.code)
        print(e.read().decode('utf-8'))

if __name__ == '__main__':
    run_test()

