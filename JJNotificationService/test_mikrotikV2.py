from routeros_api import RouterOsApiPool

api_pool = RouterOsApiPool(
    '192.168.4.1',
    username='admin',
    password='agvjrp333',
    port=8728,
    plaintext_login=True
)
api = api_pool.get_api()

queues = api.get_resource('/queue/simple')
queues.set(id='PRIVATE-ALICIA', **{'max-limit': '0/0'})
