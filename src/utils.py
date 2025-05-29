from datetime import datetime, timedelta
from sqlalchemy import or_, and_

from logger import setup_logger
from .models import UserData, UserPreference, UserImages, Match

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
logger = setup_logger("utils")

def process_potential_match(user1_id, user2_id):
    """Process potential match between two users based on their preferences"""
    # Get preferences in both directions
    pref1 = UserPreference.query.filter_by(user_id=user1_id, preferred_user_id=user2_id).first()
    pref2 = UserPreference.query.filter_by(user_id=user2_id, preferred_user_id=user1_id).first()

    # If either preference doesn't exist yet, no match to process
    if not pref1 or not pref2:
        return

    # Check if there's an existing match
    existing_match = Match.query.filter(
        or_(
            and_(Match.user1_id == user1_id, Match.user2_id == user2_id),
            and_(Match.user1_id == user2_id, Match.user2_id == user1_id)
        )
    ).first()

    # Case I: Both users like each other
    from src import db
    if pref1.preference == 'like' and pref2.preference == 'like':
        if existing_match:
            # Update match status
            existing_match.status = 'active'
            existing_match.visible_after = datetime.utcnow() + timedelta(minutes=20)
        else:
            # Create new match with 20 minute delay
            new_match = Match(
                user1_id=user1_id,
                user2_id=user2_id,
                visible_after=datetime.utcnow() + timedelta(minutes=20),
                status='active'
            )
            db.session.add(new_match)

    # Case II: One or both users rejected
    elif pref1.preference == 'reject' or pref2.preference == 'reject':
        if existing_match:
            # Mark match as deleted
            existing_match.status = 'deleted'

    # Case III & IV: Save for later scenarios
    elif pref1.preference == 'save_later' or pref2.preference == 'save_later':
        # Only proceed if neither preference is 'reject'
        if pref1.preference != 'reject' and pref2.preference != 'reject':
            if not existing_match:
                # Create pending match
                new_match = Match(
                    user1_id=user1_id,
                    user2_id=user2_id,
                    status='pending',
                    visible_after=datetime.utcnow()  # Visible immediately, but pending
                )
                db.session.add(new_match)


def get_match_score(user1_data, user2_data):
    """Calculate a simple match score between two users based on age and hobbies"""
    score = 0

    # Age compatibility
    try:
        age_diff = abs(float(user1_data.age) - float(user2_data.age))
        if age_diff <= 5:
            score += 30
        elif age_diff <= 10:
            score += 20
        elif age_diff <= 15:
            score += 10
    except (ValueError, TypeError):
        pass

    # Common hobbies
    if user1_data.hobbies and user2_data.hobbies:
        common_hobbies = set(user1_data.hobbies).intersection(set(user2_data.hobbies))
        score += min(len(common_hobbies) * 10, 30)

    return score


def get_match_status(user_id, other_user_id):
    try:

        # Get user preferences
        user_pref = UserPreference.query.filter_by(
            user_id=user_id, preferred_user_id=other_user_id
        ).first()

        other_pref = UserPreference.query.filter_by(
            user_id=other_user_id, preferred_user_id=user_id
        ).first()

        current_time = datetime.utcnow()

        matches = Match.query.filter(
            or_(
                Match.user1_id == user_id,
                Match.user2_id == user_id
            ),
            Match.status != 'deleted',
            Match.visible_after <= current_time
        ).all()
        for match in matches:
            # Determine the other user ID
            matched_user_id = match.user2_id if match.user1_id == user_id else match.user1_id

            # Checks if the required match is found else continue
            if matched_user_id != other_user_id:
                continue

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
            return [display_status, show_message_button]
        return ""
    except Exception as e:
        logger.error(f"Error in get_status: {str(e)}")
        return ""


def get_user_matches(user_id, limit=5):
    """Get top matches for a user"""
    try:
        # First get the user's gender
        user = UserData.query.filter_by(user_auth_id=user_id).first()
        if not user:
            logger.error(f"No user found for ID: {user_id}")
            return []

        # Normalize gender values for consistent comparison
        user_gender = user.gender.lower() if user.gender else None

        # Get users of opposite gender, handling different gender formats
        if user_gender == 'men' or user_gender == 'man':
            target_gender = ['Woman', 'woman', 'Women', 'women', 'Female', 'female']
        elif user_gender == 'woman' or user_gender == 'women':
            target_gender = ['Men', 'men', 'Man', 'man', 'Male', 'male']
        else:
            # If gender is something else or not specified, get any user
            target_gender = ['Men', 'men', 'Man', 'man', 'Male', 'male', 'Woman', 'woman', 'Women', 'women', 'Female',
                             'female']

        # Get existing matches and preferences to avoid duplicates
        existing_matches = Match.query.filter(
            or_(Match.user1_id == user_id, Match.user2_id == user_id),
            # and_(Match.status != 'deleted', Match.status != 'active')
            Match.status != 'deleted'
        ).all()

        existing_preferences = UserPreference.query.filter_by(user_id=user_id).all()

        # Create sets of already matched/preferred user IDs
        matched_users = set()
        for match in existing_matches:
            if match.user1_id == user_id:
                matched_users.add(match.user2_id)
            else:
                matched_users.add(match.user1_id)

        preferred_users = set([pref.preferred_user_id for pref in existing_preferences])

        # Find potential matches (users of opposite gender not already matched/preferred)
        potential_matches = UserData.query.filter(
            UserData.gender.in_(target_gender),
            UserData.user_auth_id != user_id,
            ~UserData.user_auth_id.in_(matched_users.union(preferred_users))
        ).all()

        # Calculate match scores and sort
        scored_matches = []
        for potential_match in potential_matches:
            score = get_match_score(user, potential_match)
            scored_matches.append((potential_match, score))

        # Sort by score (highest first)
        scored_matches.sort(key=lambda x: x[1], reverse=True)

        # Format results with top matches
        result = []
        for match, score in scored_matches[:limit]:
            # Get user image if available
            user_image = UserImages.query.filter_by(user_auth_id=match.user_auth_id).first()
            image_url = None
            if user_image and user_image.imageString:
                image_url = f"/uploads/{user_image.imageString}"

            result.append({
                'user_id': match.user_auth_id,
                'email': match.email,
                'firstname': match.firstname,
                'lastname': match.lastname,
                'preferences': match.preferences,
                'age': match.age,
                'bio': match.bio,
                'hobbies': match.hobbies,
                'match_score': score,
                'image_url': image_url
            })

        return result
    except Exception as e:
        logger.error(f"Error in get_user_matches: {str(e)}")
        return []


def match_all_users():
    """Match all users with someone from opposite gender"""
    try:
        # Get all users with complete profiles
        all_users = UserData.query.all()

        # Initialize results dictionary
        matches = {}

        # Get all existing matches and preferences
        existing_matches = Match.query.all()
        existing_preferences = UserPreference.query.all()

        # Create sets of user pairs who already have matches or preferences
        matched_pairs = set()
        for match in existing_matches:
            matched_pairs.add((match.user1_id, match.user2_id))
            matched_pairs.add((match.user2_id, match.user1_id))  # Add reverse pair too

        preference_pairs = set()
        for pref in existing_preferences:
            preference_pairs.add((pref.user_id, pref.preferred_user_id))

        # Group users by gender
        gender_groups = {}
        for user in all_users:
            gender = user.gender.lower() if user.gender else "unknown"
            if gender not in gender_groups:
                gender_groups[gender] = []
            gender_groups[gender].append(user)

        # Map genders to opposite genders
        opposite_genders = {
            "men": "women",
            "man": "women",
            "male": "women",
            "women": "men",
            "woman": "men",
            "female": "men"
        }

        # Process each user
        for user in all_users:
            # Skip if user already has matches in the result
            if user.user_auth_id in matches:
                continue

            user_gender = user.gender.lower() if user.gender else "unknown"

            # Determine opposite gender
            opposite_gender = opposite_genders.get(user_gender)

            # If we can't determine opposite gender, skip
            if not opposite_gender or opposite_gender not in gender_groups:
                continue

            # Find best match among opposite gender
            best_score = -1
            best_match = None

            for potential_match in gender_groups.get(opposite_gender, []):
                # Skip if they already have a match or preference
                if ((user.user_auth_id, potential_match.user_auth_id) in matched_pairs or
                        (user.user_auth_id, potential_match.user_auth_id) in preference_pairs or
                        (potential_match.user_auth_id, user.user_auth_id) in preference_pairs or
                        potential_match.user_auth_id in matches):  # Skip if already matched in this run
                    continue

                score = get_match_score(user, potential_match)
                if score > best_score:
                    best_score = score
                    best_match = potential_match

            # Create the match
            if best_match:
                # Get profile images if available
                user_image = UserImages.query.filter_by(user_auth_id=user.user_auth_id).first()
                match_image = UserImages.query.filter_by(user_auth_id=best_match.user_auth_id).first()

                user_image_url = f"/uploads/{user_image.imageString}" if user_image and user_image.imageString else None
                match_image_url = f"/uploads/{match_image.imageString}" if match_image and match_image.imageString else None

                # Add match for current user
                matches[user.user_auth_id] = {
                    'match_id': best_match.user_auth_id,
                    'firstname': best_match.firstname,
                    'age': best_match.age,
                    'score': best_score,
                    'image_url': match_image_url
                }

                # Add match for the matched user
                matches[best_match.user_auth_id] = {
                    'match_id': user.user_auth_id,
                    'firstname': user.firstname,
                    'age': user.age,
                    'score': best_score,
                    'image_url': user_image_url
                }

                # Mark this pair as matched to avoid duplicates
                matched_pairs.add((user.user_auth_id, best_match.user_auth_id))
                matched_pairs.add((best_match.user_auth_id, user.user_auth_id))

        return matches

    except Exception as e:
        logger.error(f"Error in match_all_users: {str(e)}")
        return {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS