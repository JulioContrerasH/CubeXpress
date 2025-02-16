def check_not_found_error(error_msg: str) -> bool:
    """
    Check if the error message indicates that the image was not found.
    
    Args:
        error_msg (str): The error message to check.
        
    Returns:
        bool: True if the error message indicates "not found", False otherwise.
    """
    return "not found" in error_msg