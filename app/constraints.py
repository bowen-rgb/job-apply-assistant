"""Read advertised durations without inferring candidate preferences."""
import re
import unicodedata


def advertised_duration(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text or '') if unicodedata.category(c) != 'Mn').lower()
    number = r'(1[0-2]|[1-9])'
    pattern = (r'\b(?:duree|duration|cdd|contrat|mission|stage|internship)\b'
               r'[^\n.!?]{0,50}?\b' + number + r'\s*(?:(?:a|to|[-–])\s*' + number + r'\s*)?(?:mois|months?)\b')
    for match in re.finditer(pattern, text):
        if re.search(r'experien|anciennete|probation|trial period', match[0]):
            continue
        low = int(match[1]); high = int(match[2] or low)
        if low <= high:
            return [low, high], match[0]
    return None, ''
