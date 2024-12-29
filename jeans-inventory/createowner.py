from app import db, User

def create_owner():
    owner = User(
        username='hussien',
        password='Sahs223344$',  # Use proper hashing in production
        role='owner',
        is_admin=True
    )
    db.session.add(owner)
    db.session.commit()
