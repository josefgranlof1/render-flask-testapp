from datetime import datetime
import re
from flask import Flask, jsonify, request, session,send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, send, emit
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://rework3_render_example_user:ohOZdM8RrguBuePgF9LTAgEwuzK2JR1F@dpg-cupk1kpopnds7395piq0-a.frankfurt-postgres.render.com/rework3_render_example"
socketio = SocketIO(app)
db = SQLAlchemy(app)

# Set the upload folder configuration
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure the uploads folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Task(db.Model):
    __tablename__ = 'userdetails'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(200), unique=True,nullable=False)
    password = db.Column(db.String, nullable=False)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('Task', foreign_keys=[sender_id], backref=db.backref('sent_messages', lazy=True))
    receiver = db.relationship('Task', foreign_keys=[receiver_id], backref=db.backref('received_messages', lazy=True))


class UserData(db.Model):
    __tablename__ = 'userdata'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_auth_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    firstname = db.Column(db.String(255))
    lastname = db.Column(db.String(255))
    email = db.Column(db.String(200))
    gender = db.Column(db.String(50))
    phone_number = db.Column(db.String(50))
    age = db.Column(db.String(10))
    bio = db.Column(db.Text)

    user = db.relationship('Task', backref=db.backref('user_data', lazy=True))

class RelationshipData(db.Model):
    __tablename__ = 'relationshipData'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_auth_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    email = db.Column(db.String(200))
    lookingfor = db.Column(db.String(255))
    openfor = db.Column(db.String(255))
    languages = db.Column(db.ARRAY(db.String))
    hobbies = db.Column(db.ARRAY(db.String))
    loveLanguage = db.Column(db.String(255))
    personality = db.Column(db.String(255))
    lifestyle = db.Column(db.String(255))
    family = db.Column(db.String(255))
    diet = db.Column(db.String(255))
    drinking = db.Column(db.String(255))

    user = db.relationship('Task', backref=db.backref('get_relationship_data', lazy=True))    

class LocationData(db.Model):
    __tablename__ = 'locationData'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    locationName = db.Column(db.String(200))
    lat = db.Column(db.Float)  
    lng = db.Column(db.Float) 

class UserImages(db.Model):
    __tablename__ = 'userImage'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_auth_id = db.Column(db.Integer, db.ForeignKey('userdetails.id'), nullable=False)
    email = db.Column(db.String(200))  # Ensure this column exists
    imageString = db.Column(db.String())
    user = db.relationship('Task', backref=db.backref('user_image', lazy=True))

with app.app_context():
    db.create_all()

# METHOD TO GET AUTHENTICATED USERS LIST
@app.get("/users")
def home():
    tasks = Task.query.all()
    task_list = [
        {'id': task.id, 'email': task.email, 'password': task.password} for task in tasks
    ]
    return jsonify({"user_details": task_list})

# POST USER CREDENTIALS TO DATABASE
@app.route('/users', methods=['POST'])
def postData():
    try:
        data = request.get_json()
        new_email = data.get('email')
        new_password = data.get('password')

        if not new_email or not new_password:
            return jsonify({'error': 'Email and password are required'}), 400

        # Validate email format
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, new_email):
            return jsonify({'message': 'Invalid email format'}), 400

        # Check if the email already exists
        existing_user = Task.query.filter_by(email=new_email).first()
        if existing_user:
            return jsonify({'message': 'Email already exists'}), 400

        # Create new user
        newUserDetails = Task(email=new_email, password=new_password)
        db.session.add(newUserDetails)
        db.session.commit()
        return jsonify({'message': "New User added"}), 201

    except Exception as e:
        print(e)
        return jsonify({'error': 'Internal Server Error'}), 500

# POSTING USER DATA TO DATABASE
@app.route('/userData', methods=['POST'])
def postUserData():
    try:  # Added closing parenthesis here
        data = request.get_json()
        newEmail = data['email']
        user = Task.query.filter_by(email=newEmail).first()

        if not user:
            return jsonify({'error': "No User registered with this mail"}), 400

        user_auth_id = user.id
        firstname = data['firstname']
        lastname = data['lastname']
        gender = data['gender']
        phone_number = data['phone_number']
        age = data['age']
        bio = data['bio']
    

        # Check if user details already exist
        userDetails = UserData.query.filter_by(user_auth_id=user_auth_id).first()

        if userDetails:
            # Update existing user details
            userDetails.firstname = firstname
            userDetails.lastname = lastname
            userDetails.email = newEmail
            userDetails.gender = gender
            userDetails.phone_number = phone_number
            userDetails.age = age
            userDetails.bio = bio

         
            message = "Updated user details"
        else:
            # Add new user details
            userDetails = UserData(
                user_auth_id=user_auth_id,
                firstname=firstname,
                lastname=lastname,
                email=newEmail,
                gender=gender,
                phone_number=phone_number,
                age=age,
                bio=bio,

            )
            db.session.add(userDetails)
            message = "Added user details"

        db.session.commit()
        return jsonify({'message': message}), 201

    except Exception as e:
        return jsonify({'error': 'Internal Server Error'}), 500

# POSTING Relationships DATA TO DATABASE 2025
@app.route('/relationshipData', methods=['POST'])
def postRelationshipsData():
    try:
        # Extract data from the request
        data = request.get_json()
        new_email = data['email']
        lookingfor = data['lookingfor']
        openfor = data['openfor']
        languages = data['languages']
        hobbies = data['hobbies']
        loveLanguage = data['loveLanguage']
        personality = data['personality']
        lifestyle = data['lifestyle']
        family = data['family']
        diet = data['diet']
        drinking = data['drinking']

        # Validate input
        if not new_email or not lookingfor or not openfor:
            return jsonify({"error": "Missing required fields"}), 400

        # Fetch the user by email
        user = Task.query.filter_by(email=new_email).first()

        if not user:
            return jsonify({"error": "User not found"}), 404

        user_auth_id = user.id
        lookingfor = data['lookingfor']
        openfor = data['openfor']
        languages = data['languages']
        hobbies = data['hobbies']
        loveLanguage = data['loveLanguage']
        personality = data['personality']
        lifestyle = data['lifestyle']
        family = data['family']
        diet = data['diet']
        drinking = data['drinking']

        # Check if the user already has preferences
        userrelationshipsDetails = RelationshipData.query.filter_by(user_auth_id=user_auth_id).first()

        if userrelationshipsDetails:
            # Update existing preference
            userrelationshipsDetails.lookingfor = lookingfor
            userrelationshipsDetails.openfor = openfor,
            userrelationshipsDetails.languages = languages,
            userrelationshipsDetails.hobbies = hobbies,
            userrelationshipsDetails.email = new_email,
            userrelationshipsDetails.loveLanguage = loveLanguage,
            userrelationshipsDetails.personality = personality,
            userrelationshipsDetails.lifestyle = lifestyle,
            userrelationshipsDetails.family = family,
            userrelationshipsDetails.diet = diet,
            userrelationshipsDetails.drinking = drinking,            

            message = "Updated user relationshipData"
        else:
            # Create new preference
            userrelationshipsDetails = RelationshipData(
                user_auth_id=user_auth_id,
                email=new_email,
                lookingfor=lookingfor,
                openfor=openfor,
                languages=languages,
                hobbies=hobbies,
                loveLanguage=loveLanguage,
                personality=personality,
                lifestyle=lifestyle,
                family=family,
                diet=diet,
                drinking=drinking
            )
            db.session.add(userrelationshipsDetails)
            message = "Added new user relationshipData"

        # Commit changes to the database
        db.session.commit()
        return jsonify({'message': message}), 201

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500      


@app.route('/upload_image', methods=['POST'])
def upload_image():
    try:
        # Check if the request contains a file
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
        
        file = request.files['image']
        new_email = request.form.get('email')
        
        # Check if email is provided
        if not new_email:
            return jsonify({"error": "Email is required"}), 400
        
        user = Task.query.filter_by(email=new_email).first()

        if not user:
            return jsonify({'error': "No user registered with this email"}), 400

        user_auth_id = user.id

        # Check if the file is allowed
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Save the file in the 'uploads' folder
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Check if an image already exists for this user
            user_image = UserImages.query.filter_by(user_auth_id=user_auth_id).first()

            if user_image:
                # Update existing image
                user_image.imageString = filename
                message = "Updated user image"
            else:
                # Add new image
                user_image = UserImages(
                    user_auth_id=user_auth_id,
                    email=new_email,
                    imageString=filename
                )
                db.session.add(user_image)
                message = "Added new user image"
            
            db.session.commit()

            # Generate the image URL
            image_url = request.host_url + 'uploads/' + filename
            return jsonify({"message": message, "image_url": image_url}), 201
        
        else:
            return jsonify({"error": "Invalid image format"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/get_image/<int:user_auth_id>', methods=['GET'])
def get_image(user_auth_id):
    # Query the database for a single record matching the user_auth_id
    user_image = UserImages.query.filter_by(user_auth_id=user_auth_id).first()

    if user_image:
        # Return the image as an object
        return jsonify({
            "id": user_image.id,
            "email":user_image.email,
            "user_auth_id": user_image.user_auth_id,
            "imageString": user_image.imageString
        }), 200
    else:
        return jsonify({"error": "No image found for the given user_auth_id"}), 404
    
@app.route('/userData', methods=['GET'])
def getUserData():
    try:
        # Query all user details
        userDetailsList = UserData.query.all()
        
        # Prepare the response data
        users = []
        for userDetails in userDetailsList:
            user_image = UserImages.query.filter_by(user_auth_id=userDetails.user_auth_id).first()
            
            # If user has an image, generate the image URL
            if user_image and user_image.imageString:
                image_url = request.host_url + 'uploads/' + user_image.imageString
            else:
                image_url = None  # No image available

            user = {
                'id': userDetails.user_auth_id,
                'firstname': userDetails.firstname,
                'lastname': userDetails.lastname,
                'email': userDetails.email,
                'gender': userDetails.gender,
                'phone_number': userDetails.phone_number,
                'age': userDetails.age,
                'bio': userDetails.bio,
                'image_url': image_url,  # Include the image URL in the response

            }
            users.append(user)
        
        return jsonify({'users': users}), 200
    
    except Exception as e:
        return jsonify({'error': 'Internal Server Error'}), 500

# Getting Relationships DATA FROM DATABASE 2025
@app.route('/relationshipData', methods=['GET'])
def get_relationship_data():
    relationships = RelationshipData.query.all()
    data = [
        {
            'id': rel.id,
            'user_auth_id': rel.user_auth_id,
            'email': rel.email,
            'lookingfor': rel.lookingfor,
            'openfor': rel.openfor,
            'languages': rel.languages,
            'hobbies': rel.hobbies,
            'loveLanguage': rel.loveLanguage,
            'personality': rel.personality,
            'lifestyle': rel.lifestyle,
            'family': rel.family,
            'diet': rel.diet,
            'drinking': rel.drinking,
        }
        for rel in relationships
    ]
    return jsonify(data)


@app.route('/locationData', methods=['GET'])
def getLocationData():
    locations = LocationData.query.all()
    data = [
        {
            'id': loc.id,
            'locationName': loc.locationName,
            'lat': loc.lat,
            'lng': loc.lng,

        }
        for loc in locations
    ]
    return jsonify(data)


# USER SIGNIN METHOD
@app.route('/sign-in', methods=['POST'])
def sign_in():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400

        user = Task.query.filter_by(email=email).first()

        if user:
            if password == user.password:  # Compare passwords directly
                return jsonify({'message': 'Sign in successful'}), 200
            else:
                return jsonify({'message': 'Invalid credentials'}), 401
        else:
            return jsonify({'message': 'Invalid credentials'}), 401

    except Exception as e:
        return jsonify({'error': 'Internal Server Error'}), 500



@app.route('/send_message', methods=['POST'])
def send_message():
    sender_email = request.form.get('sender_email')
    receiver_email = request.form.get('receiver_email')
    message = request.form.get('message')

    # Check if any of the fields are missing
    if not sender_email or not receiver_email or not message:
        return jsonify({'error': 'Missing data'}), 400

    # Look up user IDs based on emails
    sender = Task.query.filter_by(email=sender_email).first()
    receiver = Task.query.filter_by(email=receiver_email).first()

    if not sender or not receiver:
        return jsonify({'error': 'Sender or receiver not found'}), 404

    # Store the message in the database
    new_message = Message(sender_id=sender.id, receiver_id=receiver.id, message=message)
    db.session.add(new_message)
    db.session.commit()

    # Emit the message to the receiver's room using receiver's email
    socketio.emit('receive_message', {
        'sender_email': sender_email,
        'receiver_email': receiver_email,
        'message': message
    }, room=receiver_email)

    return jsonify({'status': 'Message sent'})


@socketio.on('send_message')
def handle_message(data):
    sender_email = data['sender_email']
    receiver_email = data['receiver_email']
    message = data['message']

    # Look up user IDs based on emails
    sender = Task.query.filter_by(email=sender_email).first()
    receiver = Task.query.filter_by(email=receiver_email).first()

    if not sender or not receiver:
        emit('error', {'error': 'Sender or receiver not found'})
        return

    # Store the message in the database
    new_message = Message(sender_id=sender.id, receiver_id=receiver.id, message=message)
    db.session.add(new_message)
    db.session.commit()

    # Emit the message to the receiver's room using receiver's email
    emit('receive_message', {
        'sender_email': sender_email,
        'receiver_email': receiver_email,
        'message': message
    }, room=receiver_email)


@socketio.on('join')
def on_join(data):
    user_email = data['user_email']
    user = Task.query.filter_by(email=user_email).first()

    if not user:
        emit('error', {'error': 'User not found'})
        return

    join_room(user_email)  # Join the room based on email
    emit('status', {'msg': f'User {user_email} has entered the room.'}, room=user_email)

    
@app.route('/get_chats', methods=['GET'])
def get_chats():
    email1 = request.args.get('email1')
    email2 = request.args.get('email2')

    if not email1 or not email2:
        return jsonify({'error': 'Missing email addresses'}), 400

    # Retrieve user IDs based on the provided emails
    user1 = Task.query.filter_by(email=email1).first()
    user2 = Task.query.filter_by(email=email2).first()

    if not user1 or not user2:
        return jsonify({'error': 'One or both users not found'}), 404

    # Fetch the chat history between the two users
    messages = Message.query.filter(
        ((Message.sender_id == user1.id) & (Message.receiver_id == user2.id)) |
        ((Message.sender_id == user2.id) & (Message.receiver_id == user1.id))
    ).order_by(Message.timestamp).all()

    # Prepare the chat history for response, adding sender and receiver emails
    chat_history = [
        {
            'sender_id': msg.sender_id,
            'sender_email': user1.email if msg.sender_id == user1.id else user2.email,
            'receiver_id': msg.receiver_id,
            'receiver_email': user2.email if msg.receiver_id == user2.id else user1.email,
            'message': msg.message,
            'timestamp': msg.timestamp
        }
        for msg in messages
    ]

    return jsonify(chat_history)


    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)