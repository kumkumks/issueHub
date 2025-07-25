import random
import string


def generate_unique_slug(instance, base_slug):
    """
    Generates a unique slug for a given model instance by appending a 4-character
    alphanumeric code to a base slug. Ensures the generated slug is unique within
    the model's database table.
    Args:
        instance: The model instance for which the slug is being generated. The
            instance's class is used to query the database for existing slugs.
        base_slug (str): The base string to which the unique code will be appended.
    Returns:
        str: A unique slug in the format "{base_slug}-{unique_code}".
    Raises:
        AttributeError: If the model class does not have a `objects.filter` method
            to query the database.
    """
    """Generates a unique slug with a 4-character alphanumeric code."""
    def generate_code():
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    
    slug = f"{base_slug}-{generate_code()}"
    model_class = instance.__class__
    while model_class.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{generate_code()}"
    return slug


def generate_unique_code(model, no_of_char=6, unique_field='id'):
    """
    Generates a unique alphanumeric code for a given model by checking for uniqueness in the specified field.
    Args:
        model: An instance of the Django model for which the unique code is to be generated.
        no_of_char (int, optional): The length of the generated code. Defaults to 6.
        unique_field (str, optional): The name of the model field that should be unique. Defaults to 'id'.
    Returns:
        str: A unique alphanumeric code of the specified length.
    Notes:
        - The function generates random codes consisting of lowercase letters and digits.
        - It checks the database to ensure the generated code does not already exist in the specified field.
        - The function assumes the model has a manager named 'objects' and supports the 'filter' and 'exists' methods.
    """
    def generate_code():
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=no_of_char))
    
    code = generate_code()
    filter_kwargs = {unique_field: code}
    model_class = model.__class__
    while model_class.objects.filter(**filter_kwargs).exists():
        code = generate_code()
    return code