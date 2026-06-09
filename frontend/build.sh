#!/bin/bash
pip install -r requirements.txt
prisma generate --schema=./backend/prisma/schema.prisma
