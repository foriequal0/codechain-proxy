#!/usr/bin/env python3
import argparse
import aiohttp
from aiohttp import web
import logging
import sys
from logging.handlers import RotatingFileHandler
import json

def create(whitelist="whitelist.txt", forward=8080, log="proxy.log", **kwargs):
    handler = RotatingFileHandler(log, maxBytes=0x100000, backupCount=3)
    handler.setFormatter(RequestFormatter())
    logger = logging.getLogger("Proxy")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler(sys.stderr))

    with open(whitelist) as f:
        whitelist_set = set(line.rstrip() for line in f)
        
    def error_msg(code, msg, id, status):
        id = "null" if id is None else id
        return web.json_response (
            data={ "jsonrpc": "2.0", "error": {"code": code, "message": msg}, "id": id},
            status=status
        )

    def invalid_request():
        return error_msg(-32600, "Invalid request", None, 400)

    def method_not_found(id):
        return error_msg(-32601, "Method not found", id, 404)

    def internal_error(id):
        return error_msg(-32603, "Internal error", id, 500)

    forward_addr = 'http://localhost:{}'.format(forward)

    async def proxy(request):
        try:
            text = await request.text()
            content = json.loads(text)
        except:
            logger.exception('Request is a invalid JSON')
            return invalid_request()

        if 'id' not in content or 'method' not in content:
            return web.Response()
        
        if content['method'] not in whitelist_set:
            logger.error('Filtered {}:{}}'.format(content['method'], text))
            return method_not_found(content['id'])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(forward_addr, json=content) as resp:
                    response = await resp.text()

            logger.info('Successfully forwarded {} / Response {}'.format(text, response.strip()))
            return web.Response(text=response, content_type='application/json')
        except Exception as e:
            logger.error('Failed to receive the response from the server: {}'.format(e))
            return internal_error(content['id'])
    
    app = web.Application()
    app.add_routes([web.post('/', proxy)])
    return app

class RequestFormatter(logging.Formatter):
    def __init__(self, fmt=None, **kwargs):
        default_fmt = '[%(asctime)s] [%(levelname)s in %(module)s] %(message)s'
        if fmt is None:
            super().__init__(fmt=default_fmt, **kwargs)
        else:
            super().__init__(**kwargs)

    def format(self, record):
        return super(RequestFormatter, self).format(record)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--whitelist', default='whitelist.txt',
                        help='whitelist file path (default: \"whiltelist.txt\")')
    parser.add_argument('--bind', default='0.0.0.0',
                        help='binding address (default: 0.0.0.0)')
    parser.add_argument('--port', type=int,
                        help='binding port')
    parser.add_argument('--forward', type=int, default=8080,
                        help='port to forward (deafult: 8080)')
    parser.add_argument('--log', default='proxy.log',
                        help='log file path (default: \"proxy.log\")')

    args = parser.parse_args()
    app = create(**vars(args))
    web.run_app(app, host=args.bind, port=args.port)