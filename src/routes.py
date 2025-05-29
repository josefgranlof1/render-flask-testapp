from flask_socketio import join_room, emit
from .models import Task, UserPreference, Match, RelationshipData, UserData, UserImages, Message
import re, os
from flask import request, jsonify, send_from_directory
from src import db, socketio, bcrypt, limiter
from .utils import process_potential_match, match_all_users, allowed_file
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import or_
from logger import setup_logger
from flask import Blueprint
from flask_login import login_required

logger = setup_logger("routes")
users_app = Blueprint("users", __name__)


@limiter.exempt
@users_app.route('/', methods=['GET'])
def healthcheck():
    return jsonify({"success": "Welcome to health-check page. The server is up and running."})


@login_required
@users_app.route('/preference', methods=['POST'])
def set_preference():
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        preferred_user_email = data.get('preferred_user_email')
        preference = data.get('preference')  # 'like', 'reject', 'save_later'

        # Validate inputs
        if not user_email or not preferred_user_email or not preference:
            logger.error('Missing required fields')
            return jsonify({'error': 'Missing required fields'}), 400

        if preference not in ['like', 'reject', 'save_later']:
            logger.error('Invalid preference type')
            return jsonify({'error': 'Invalid preference type'}), 400

        # Get user IDs from emails
        user = Task.query.filter_by(email=user_email).first()
        preferred_user = Task.query.filter_by(email=preferred_user_email).first()

        if not user or not preferred_user:
            logger.error('One or both users not found')
            return jsonify({'error': 'One or both users not found'}), 404

        # Check if preference already exists
        existing_preference = UserPreference.query.filter_by(
            user_id=user.id,
            preferred_user_id=preferred_user.id
        ).first()

        if existing_preference:
            # Update existing preference
            logger.info("Updating existing preference.")
            existing_preference.preference = preference
            existing_preference.timestamp = datetime.utcnow()
        else:
            # Create new preference
            logger.info("Creating new preference.")
            new_preference = UserPreference(
                user_id=user.id,
                preferred_user_id=preferred_user.id,
                preference=preference
            )
            db.session.add(new_preference)

        # Check if this creates a match
        process_potential_match(user.id, preferred_user.id)

        db.session.commit()

        logger.info(f'Preference set to {preference}')
        return jsonify({'message': f'Preference set to {preference}'}), 201

    except Exception as e:
        logger.info(f"Error in set_preference: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@login_required
@users_app.route('/matches/<email>', methods=['GET'])
def get_user_matches(email):
    try:
        user = Task.query.filter_by(email=email).first()
        if not user:
            logger.error('User not found')
            return jsonify({'error': 'User not found'}), 404

        # Get all matches for this user that are visible now
        current_time = datetime.utcnow()
        matches = Match.query.filter(
            or_(
                Match.user1_id == user.id,
                Match.user2_id == user.id
            ),
            Match.status != 'deleted',
            Match.visible_after <= current_time
        ).all()

        # Format the response
        result = []
        for match in matches:
            # Determine the other user ID
            other_user_id = match.user2_id if match.user1_id == user.id else match.user1_id
            other_user = Task.query.get(other_user_id)
            other_user_data = UserData.query.filter_by(user_auth_id=other_user_id).first()

            if not other_user or not other_user_data:
                continue

            # Get user preferences
            user_pref = UserPreference.query.filter_by(
                user_id=user.id, preferred_user_id=other_user_id
            ).first()

            other_pref = UserPreference.query.filter_by(
                user_id=other_user_id, preferred_user_id=user.id
            ).first()

            # Determine match status from user's perspective
            if match.status == 'active':
                # Both liked each other
                display_status = 'matched'
                show_message_button = True
            else:  # status is 'pending'
                if user_pref and user_pref.preference == 'save_later':
                    display_status = 'decide'  # User needs to decide
                    show_message_button = False
                elif other_pref and other_pref.preference == 'save_later':
                    display_status = 'pending'  # Waiting for other user
                    show_message_button = False
                else:
                    display_status = 'pending'  # Generic pending
                    show_message_button = False

            # Get profile image
            user_image = UserImages.query.filter_by(user_auth_id=other_user_id).first()
            image_url = None
            if user_image and user_image.imageString:
                image_url = request.host_url + 'uploads/' + user_image.imageString

            # Add match to result
            result.append({
                'match_id': match.id,
                'user_id': other_user_id,
                'firstname': other_user_data.firstname,
                'email': other_user.email,
                'age': other_user_data.age,
                'bio': other_user_data.bio,
                'status': display_status,
                'show_message_button': show_message_button,
                'match_date': match.match_date,
                'image_url': image_url
            })

        return jsonify({'matches': result}), 200

    except Exception as e:
        logger.info(f"Error in get_user_matches: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@login_required
@users_app.route('/update_match_status', methods=['POST'])
def update_match_status():
    try:
        data = request.get_json()
        match_id = data.get('match_id')
        user_email = data.get('user_email')
        decision = data.get('decision')  # 'accept' or 'reject'

        # Validate inputs
        if not match_id or not user_email or not decision:
            logger.error('Missing required fields')
            return jsonify({'error': 'Missing required fields'}), 400

        if decision not in ['accept', 'reject']:
            logger.error('Invalid decision')
            return jsonify({'error': 'Invalid decision'}), 400

        # Get user
        user = Task.query.filter_by(email=user_email).first()
        if not user:
            logger.error('User not found')
            return jsonify({'error': 'User not found'}), 404

        # Get match
        match = Match.query.get(match_id)
        if not match:
            logger.error('Match not found')
            return jsonify({'error': 'Match not found'}), 404

        # Verify user is part of this match
        if match.user1_id != user.id and match.user2_id != user.id:
            logger.error('User not authorized to update this match')
            return jsonify({'error': 'User not authorized to update this match'}), 403

        # Determine other user ID
        other_user_id = match.user2_id if match.user1_id == user.id else match.user1_id

        # Update user preference based on decision
        if decision == 'accept':
            pref = UserPreference.query.filter_by(
                user_id=user.id, preferred_user_id=other_user_id
            ).first()

            if pref:
                pref.preference = 'like'
            else:
                new_pref = UserPreference(
                    user_id=user.id,
                    preferred_user_id=other_user_id,
                    preference='like'
                )
                db.session.add(new_pref)

            # Check if this creates a match
            process_potential_match(user.id, other_user_id)

        else:  # decision == 'reject'
            pref = UserPreference.query.filter_by(
                user_id=user.id, preferred_user_id=other_user_id
            ).first()

            if pref:
                pref.preference = 'reject'
            else:
                new_pref = UserPreference(
                    user_id=user.id,
                    preferred_user_id=other_user_id,
                    preference='reject'
                )
                db.session.add(new_pref)

            # Mark match as deleted
            match.status = 'deleted'

        db.session.commit()

        logger.info(f'Match {decision}ed successfully')
        return jsonify({'message': f'Match {decision}ed successfully'}), 200

    except Exception as e:
        logger.error(f"Error in update_match_status: {str(e)}")
        return jsonify({'error': 'Internal Server Error'}), 500


@login_required
@users_app.route('/match/<int:user_id>', methods=['GET'])
def get_matches_endpoint(user_id):
    # todo: need to pass email to this function, not user_id
    matches = get_user_matches(user_id)
    logger.info(f"Returning matches endpoint for user: {user_id}")
    return jsonify({
        'user_id': user_id,
        'matches': matches
    })


# Get all users best matches
@login_required
@users_app.route('/matches', methods=['GET'])
def get_all_matches():
    matches = match_all_users()
    logger.info("Returning matches.")
    return jsonify({'matches': matches})


# METHOD TO GET AUTHENTICATED USERS LIST
@login_required
@users_app.get("/users")
def home():
    tasks = Task.query.all()
    task_list = [
        {'id': task.id, 'email': task.email, 'password': task.password} for task in tasks
    ]
    logger.info("Returning users")
    return jsonify({"user_details": task_list})


# POST USER CREDENTIALS TO DATABASE
@users_app.route('/users', methods=['POST'])
def postData():
    try:
        data = request.get_json()
        new_email = data.get('email')
        new_password = data.get('password')

        if not new_email or not new_password:
            logger.error('Email and password are required')
            return jsonify({'error': 'Email and password are required'}), 400

        # Validate email format
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, new_email):
            logger.error('Invalid email format')
            return jsonify({'message': 'Invalid email format'}), 400

        # Check if the email already exists
        existing_user = Task.query.filter_by(email=new_email).first()
        if existing_user:
            logger.error('Email already exists')
            return jsonify({'message': 'Email already exists'}), 400

        # create a hashed password from the raw password
        hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        # Create new user
        new_user_details = Task(email=new_email, password=hashed_password)
        db.session.add(new_user_details)
        db.session.commit()
        logger.info("New User added")
        return jsonify({'message': "New User added"}), 201

    except Exception as e:
        logger.error(f"Exception occurred- {e}")
        return jsonify({'error': 'Internal Server Error'}), 500


# POSTING USER DATA TO DATABASE
@login_required
@users_app.route('/userData', methods=['POST'])
def postUserData():
    try:  # Added closing parenthesis here
        data = request.get_json()
        newEmail = data.get('email')
        user = Task.query.filter_by(email=newEmail).first()

        if not user:
            logger.error("No User registered with this mail")
            return jsonify({'error': "No User registered with this mail"}), 400

        user_auth_id = user.id
        firstname = data.get('firstname')
        lastname = data.get('lastname')
        gender = data.get('gender')
        hobbies = data.get('hobbies')
        preferences = data.get('preferences')
        phone_number = data.get('phone_number')
        age = data.get('age')
        bio = data.get('bio')

        # Check if user details already exist
        userDetails = UserData.query.filter_by(user_auth_id=user_auth_id).first()

        if userDetails:
            # Update existing user details
            userDetails.firstname = firstname
            userDetails.lastname = lastname
            userDetails.email = newEmail
            userDetails.gender = gender
            userDetails.hobbies = hobbies
            userDetails.preferences = preferences
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
                hobbies=hobbies,
                preferences=preferences,
                phone_number=phone_number,
                age=age,
                bio=bio
            )
            db.session.add(userDetails)
            message = "Added user details"

        db.session.commit()
        logger.info(message)
        return jsonify({'message': message}), 201

    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500


# POSTING Relationships DATA TO DATABASE 2025
@login_required
@users_app.route('/relationshipData', methods=['POST'])
def postRelationshipsData():
    try:
        # Extract data from the request
        data = request.get_json()
        new_email = data.get('email')
        lookingfor = data.get('lookingfor')
        openfor = data.get('openfor')

        # Validate input
        if not new_email or not lookingfor or not openfor:
            logger.error("Missing required fields")
            return jsonify({"error": "Missing required fields"}), 400

        # Fetch the user by email
        user = Task.query.filter_by(email=new_email).first()

        if not user:
            logger.error("User not found")
            return jsonify({"error": "User not found"}), 404

        user_auth_id = user.id
        lookingfor = data.get('lookingfor')
        openfor = data.get('openfor')

        # Check if the user already has preferences
        userrelationshipsDetails = RelationshipData.query.filter_by(user_auth_id=user_auth_id).first()

        if userrelationshipsDetails:
            # Update existing preference
            userrelationshipsDetails.lookingfor = lookingfor
            userrelationshipsDetails.openfor = openfor
            userrelationshipsDetails.email = new_email

            message = "Updated user relationshipData"
        else:
            # Create new preference
            userrelationshipsDetails = RelationshipData(
                user_auth_id=user_auth_id,
                email=new_email,
                lookingfor=lookingfor,
                openfor=openfor
            )
            db.session.add(userrelationshipsDetails)
            message = "Added new user relationshipData"

        # Commit changes to the database
        db.session.commit()
        logger.info(message)
        return jsonify({'message': message}), 201

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500


@login_required
@users_app.route('/upload_image', methods=['POST'])
def upload_image():
    try:
        # Check if the request contains a file
        if 'image' not in request.files:
            logger.error("No image file provided")
            return jsonify({"error": "No image file provided"}), 400

        file = request.files['image']
        new_email = request.form.get('email')

        # Check if email is provided
        if not new_email:
            logger.error("Email is required")
            return jsonify({"error": "Email is required"}), 400

        user = Task.query.filter_by(email=new_email).first()

        if not user:
            logger.error("No user registered with this email")
            return jsonify({'error': "No user registered with this email"}), 400

        user_auth_id = user.id

        # Check if the file is allowed
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Save the file in the 'uploads' folder
            from src import UPLOAD_FOLDER
            file_path = os.path.join(UPLOAD_FOLDER, filename)
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
            logger.info(message)
            return jsonify({"message": message, "image_url": image_url}), 201

        else:
            logger.error("Invalid image format")
            return jsonify({"error": "Invalid image format"}), 400

    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        return jsonify({"error": str(e)}), 500


@login_required
@users_app.route('/uploads/<filename>')
def uploaded_file(filename):
    from src import UPLOAD_FOLDER
    return send_from_directory(UPLOAD_FOLDER, filename)


@login_required
@users_app.route('/get_image/<int:user_auth_id>', methods=['GET'])
def get_image(user_auth_id):
    # Query the database for a single record matching the user_auth_id
    user_image = UserImages.query.filter_by(user_auth_id=user_auth_id).first()

    if user_image:
        # Return the image as an object
        logger.info("Returning image")
        return jsonify({
            "id": user_image.id,
            "email": user_image.email,
            "user_auth_id": user_image.user_auth_id,
            "imageString": user_image.imageString
        }), 200
    else:
        logger.error("No image found for the given user_auth_id")
        return jsonify({"error": "No image found for the given user_auth_id"}), 404


@login_required
@users_app.route('/userData', methods=['GET'])
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
                'hobbies': userDetails.hobbies,
                'preferences': userDetails.preferences,
                'phone_number': userDetails.phone_number,
                'age': userDetails.age,
                'bio': userDetails.bio,
                'image_url': image_url  # Include the image URL in the response
            }
            users.append(user)

        logger.info("Returning user data")
        return jsonify({'users': users}), 200

    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500


# Getting Relationships DATA FROM DATABASE 2025
@login_required
@users_app.route('/relationshipData', methods=['GET'])
def get_relationship_data():
    relationships = RelationshipData.query.all()
    data = [
        {
            'id': rel.id,
            'user_auth_id': rel.user_auth_id,
            'email': rel.email,
            'lookingfor': rel.lookingfor,
            'openfor': rel.openfor
        }
        for rel in relationships
    ]
    logger.info("Returning relationship data")
    return jsonify(data)


# USER SIGNIN METHOD
@users_app.route('/sign-in', methods=['POST'])
def sign_in():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            logger.error('Email and password are required')
            return jsonify({'error': 'Email and password are required'}), 400

        user = Task.query.filter_by(email=email).first()

        if user:
            # compare hashed password instead of direct password
            if bcrypt.check_password_hash(user.password, password):
                logger.info('Sign in successful')
                return jsonify({'message': 'Sign in successful'}), 200
            else:
                logger.error('Invalid credentials')
                return jsonify({'message': 'Invalid credentials'}), 401
        else:
            logger.error('Invalid credentials')
            return jsonify({'message': 'Invalid credentials'}), 401

    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500


# Getting Sign-in DATA
@users_app.route('/sign-in', methods=['GET'])
def get_signin_data():
    signin = Task.query.all()
    data = [
        {
            'id': rel.id,
            'email': rel.email,
            'password': rel.password,
        }
        for rel in signin
    ]
    logger.info("Returning sign-in data")
    return jsonify(data)


@login_required
@users_app.route('/send_message', methods=['POST'])
def send_message():
    sender_email = request.form.get('sender_email')
    receiver_email = request.form.get('receiver_email')
    message = request.form.get('message')

    # Check if any of the fields are missing
    if not sender_email or not receiver_email or not message:
        logger.error('Missing data')
        return jsonify({'error': 'Missing data'}), 400

    # Look up user IDs based on emails
    sender = Task.query.filter_by(email=sender_email).first()
    receiver = Task.query.filter_by(email=receiver_email).first()

    if not sender or not receiver:
        logger.error('Sender or receiver not found')
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

    logger.info('Message sent')
    return jsonify({'status': 'Message sent'})


@socketio.on('send_message')
def handle_message(data):
    sender_email = data.get('sender_email')
    receiver_email = data.get('receiver_email')
    message = data.get('message')

    # Look up user IDs based on emails
    sender = Task.query.filter_by(email=sender_email).first()
    receiver = Task.query.filter_by(email=receiver_email).first()

    if not sender or not receiver:
        logger.error('Sender or receiver not found')
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
    user_email = data.get('user_email')
    user = Task.query.filter_by(email=user_email).first()

    if not user:
        logger.error('User not found')
        emit('error', {'error': 'User not found'})
        return

    join_room(user_email)  # Join the room based on email
    logger.info(f'User {user_email} has entered the room.')
    emit('status', {'msg': f'User {user_email} has entered the room.'}, room=user_email)


@login_required
@users_app.route('/get_chats', methods=['GET'])
def get_chats():
    email1 = request.args.get('email1')
    email2 = request.args.get('email2')
    if not email1 or not email2:
        logger.error('Missing email addresses')
        return jsonify({'error': 'Missing email addresses'}), 400

    # Retrieve user IDs based on the provided emails
    user1 = Task.query.filter_by(email=email1).first()
    user2 = Task.query.filter_by(email=email2).first()

    if not user1 or not user2:
        logger.error('One or both users not found')
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
