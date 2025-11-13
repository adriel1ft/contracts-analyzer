import re

def anonymize_text(text):
    text = re.sub(r"R\$ ?")