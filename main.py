import random, uuid, datetime
from flask import Flask, request
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv
import os

def create_app(testing: bool = True):
    app = Flask(__name__)

    registerd_languages = ['en', 'de']

    jokes = {}
    antijokes = {}

    load_dotenv()

    print('Connecting to database...')

    mydb = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )
    print('Connected to database. Loading statements...')
    mycursor = mydb.cursor()

    for language in registerd_languages:
        mycursor.execute("SELECT * FROM jokes_" + language)
        jokes_result = mycursor.fetchall()
        mycursor.execute("SELECT * FROM antijokes_" + language)
        antijokes_result = mycursor.fetchall()

        jokes[language] = [joke[0] for joke in jokes_result]
        antijokes[language] = [antijoke[0] for antijoke in antijokes_result]

    print('Successfully loaded statements.')

    print(jokes['de'][0])
    print(antijokes['de'][0])
    print(jokes['en'][0])
    print(antijokes['en'][0])

    CORS(app)

    challenges = {}
    valid_tokens = {}
    amount = 4
    

    class Challenge:
        def __init__(self, ip_address, language='de'):
            self.id = str(uuid.uuid4())
            statements = [i for i in random.sample(jokes[language], random.randint(1, amount))]
            joke_strings = statements.copy()

            for _ in range(amount - len(statements)):
                sentence = random.choice(antijokes[language])
                statements.append(sentence)

            random.shuffle(statements)

            self.statements = statements
            self.solution = [statements.index(joke) for joke in joke_strings]
            self.timestamp = datetime.datetime.now()
            self.ip_address = ip_address
            self.language = language or 'de'

        def getStatementObjects(self):
            return [{'id': i, 'statement': statement} for (i, statement) in enumerate(self.statements)]

    @app.get('/hutcha/v1/challenge')
    def generate_challenge():
        language = request.args.get('lang') or 'de'
        if language not in registerd_languages:
            return {'success': False, 'message': 'Language not supported.', 'supportedLanguages': registerd_languages}, 400

        challenge = Challenge(request.headers['X-Real-IP'] if 'X-Real-IP' in request.headers else request.remote_addr, language)
        challenges[challenge.id] = challenge

        return {'id': challenge.id, 'amount': amount, 'language': language, 'statements': challenge.getStatementObjects()}, 201

    @app.get('/hutcha/v1/challenge/<id>')
    def get_challenge(id):
        challenge = challenges[id] if id in challenges else None

        if challenge is None:
            return {'success': False, 'message': 'Challenge not found.'}, 404

        ip = request.headers['X-Real-IP'] if 'X-Real-IP' in request.headers else request.remote_addr

        if challenge.ip_address != ip:
            return {'success': False, 'message': 'Challenge was generated for a different IP address.'}, 403

        return {'id': challenge.id, 'amount': amount, 'language': challenge.language, 'statements': challenge.getStatementObjects()}


    @app.post('/hutcha/v1/submit/<id>')
    def submit_challenge(id):
        challenge = challenges[id] if id in challenges else None

        if challenge is None:
            return {'success': False, 'message': 'Challenge not found.'}, 404

        ip = request.headers['X-Real-IP'] if 'X-Real-IP' in request.headers else request.remote_addr
        if challenge.ip_address != ip:
            return {'success': False, 'message': 'Challenge was generated for a different IP address.'}, 403

        answers = request.json['answers']

        if set(answers) != set(challenge.solution):
            return {'success': False, 'message': 'Wrong solution. Please try again.'}, 401

        del challenges[id]
        token = str(uuid.uuid4())
        valid_tokens[token] = challenge.ip_address

        return {'success': True, 'message': 'Successfully solved the challenge.', 'token': token}, 200


    @app.post('/hutcha/v1/check-token')
    def check_token():
        body = request.json
        token = body['token'] if 'token' in body else None
        ip_address = body['ipAddress'] if 'ipAddress' in body else None

        if token is None or ip_address is None:
            return {'success': False, 'message': 'Invalid request.'}, 400

        if token not in valid_tokens:
            return {'success': False, 'message': 'Token is invalid.'}, 401

        if valid_tokens[token] != ip_address:
            return {'success': False, 'message': 'Token was generated for a different IP address.'}, 403

        valid_tokens.pop(token)
        return {'success': True, 'message': 'Token is valid.'}, 200

    return app

if __name__ == '__main__':
    app = create_app()
    app.run()
