# backend/debug.py

def debug(*args, **kwargs):
    print("[DEBUG]", *args)

def log(*args, **kwargs):
    print("[LOG]", *args)

class Debug:
    pass