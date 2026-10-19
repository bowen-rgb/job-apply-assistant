from typing import Literal
from pydantic import BaseModel,Field,ConfigDict,field_validator,model_validator
from .pfe import public_url

class PFESettings(BaseModel):
 model_config=ConfigDict(extra='forbid')
 enabled:bool=False
 use_jobspy:bool=True
 directions:list[Literal['mechanical','control','robotics','digital_twin','instrumentation','embodied_ai']]=Field(default_factory=list,max_length=6)
 locations:list[str]=Field(default_factory=lambda:['France'],max_length=10)
 start_month:str=Field(default='',pattern=r'^(?:20\d{2}-(?:0[1-9]|1[0-2]))?$')
 duration_months:int=Field(default=6,ge=1,le=12)
 start_flexibility_months:int=Field(default=1,ge=0,le=6)
 phd_goal:bool=False
 skills:list[str]=Field(default_factory=list,max_length=50)
 school_portal_url:str=Field(default='',max_length=2000)
 searxng_url:str=Field(default='',max_length=1000)
 research_sources:bool=True
 team_discovery:bool=True
 @model_validator(mode='after')
 def selected_direction(self):
  if self.enabled and not self.directions:
   raise ValueError('Select at least one professional direction')
  return self
 @field_validator('locations','skills')
 @classmethod
 def clean(cls,value):
  if any(len(s)>120 for s in value):raise ValueError('Use short location and skill labels')
  return list(dict.fromkeys(s.strip() for s in value if s.strip()))
 @field_validator('school_portal_url')
 @classmethod
 def portal(cls,value):
  if value and not public_url(value):raise ValueError('Use a public school portal URL')
  return value
 @field_validator('searxng_url')
 @classmethod
 def endpoint(cls,value):
  if value:
   from .pfe_discovery import searx_endpoint
   searx_endpoint(value)
  return value
