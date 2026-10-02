"""Reusable field types for request and response schemas."""

from typing import Annotated

from pydantic import AfterValidator, EmailStr, Field, StringConstraints

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]

# International format, digits only after an optional leading "+", e.g. +923001234567.
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9]{10,15}$")]

# Emails are stored lower-cased so uniqueness is case-insensitive.
Email = Annotated[EmailStr, AfterValidator(str.lower)]

Password = Annotated[str, Field(min_length=8, max_length=128)]

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
