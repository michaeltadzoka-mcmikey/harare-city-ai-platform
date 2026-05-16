#!/usr/bin/env python
from dashboard import create_app
from config import Config
from dashboard.routes import public_chat   # new import

app = create_app(Config)

#
app.register_blueprint(public_chat.bp)

if __name__ == '__main__':
    app.run(host=app.config['HOST'], port=app.config['PORT'])