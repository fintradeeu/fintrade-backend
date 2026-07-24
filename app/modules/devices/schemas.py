from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class DeviceRegisterRequest(BaseModel):
    deviceId: str = Field(..., alias="deviceId")
    deviceName: Optional[str] = Field(None, alias="deviceName")
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    platform: Optional[str] = None
    osName: Optional[str] = Field(None, alias="osName")
    osVersion: Optional[str] = Field(None, alias="osVersion")
    appVersion: Optional[str] = Field(None, alias="appVersion")
    buildNumber: Optional[str] = Field(None, alias="buildNumber")
    language: Optional[str] = None
    timezone: Optional[str] = None
    screenWidth: Optional[int] = Field(None, alias="screenWidth")
    screenHeight: Optional[int] = Field(None, alias="screenHeight")
    fcmToken: Optional[str] = Field(None, alias="fcmToken")
    networkType: Optional[str] = Field(None, alias="networkType")
    batteryLevel: Optional[float] = Field(None, alias="batteryLevel")
    isEmulator: Optional[bool] = Field(False, alias="isEmulator")

class DeviceLocationRequest(BaseModel):
    latitude: float
    longitude: float
    permission: str

class DeviceNotificationRequest(BaseModel):
    permission: str
    fcmToken: Optional[str] = Field(None, alias="fcmToken")

class ContactInfo(BaseModel):
    name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None

class DeviceContactsRequest(BaseModel):
    permission: str
    contacts: Optional[List[ContactInfo]] = []

class DeviceContextRequest(BaseModel):
    permission: str

class SuccessResponse(BaseModel):
    success: bool
    message: str
