# from https://flask.palletsprojects.com/en/1.1.x/tutorial/factory/
#
# import os
# from flask import Flask
# from toolbox import test_bed_path
#
#
# def create_app(test_config=None):
#     # create and configure the app
#     app = Flask(__name__, instance_relative_config=True)
#     # app.config.from_mapping(
#     #     SECRET_KEY='dev',
#     # )
#
#     if test_config is None:
#         pass
#         # load the instance config, if it exists, when not testing
#         # app.config.from_pyfile('config.py', silent=True)
#     else:
#         # load the test config if passed in
#         app.config.from_mapping(test_config)
#
#     # ensure the instance folder exists
#     try:
#         os.makedirs(app.instance_path)
#     except OSError:
#         pass
#
#     from . import web_pages
#     app.register_blueprint(web_pages.bp)
#     app.add_url_rule('/', endpoint='index')
#
#     from logic.orm import close_db_session
#     app.teardown_appcontext(close_db_session)
#
#
#     return app