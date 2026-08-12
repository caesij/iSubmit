def validate_portal_access(user, login_type):
    if login_type == 'FACULTY':
        if not user.is_faculty:
            return False, 'Only Faculty accounts can sign in through this tab.'
    elif login_type == 'ADMIN':
        if user.is_faculty:
            return False, 'Faculty members must sign in through the Faculty tab.'
        if not (user.is_admin or user.is_staff_role):
            return False, 'Access denied. Only Admin or Staff accounts can sign in here.'
            
    return True, None