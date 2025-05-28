#!/bin/bash

# Read the version from the version.txt file
VERSION=$(cat version.txt)

# Fetch the latest changes from the remote repository
git fetch origin

# Reset the local branch to match the remote branch for the specified version
git reset --hard origin/v$VERSION

echo "VPS has been reset to the latest commit from version $VERSION." 