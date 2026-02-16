#!/usr/bin/env python3
"""
KO Companion - Mobile Entry Point
=================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Voice-first offline AI companion for mobile devices.
"""

import os
import sys

# Set environment for mobile
os.environ['KIVY_LOG_LEVEL'] = 'info'

from app.main import KOCompanionApp

if __name__ == '__main__':
    KOCompanionApp().run()
