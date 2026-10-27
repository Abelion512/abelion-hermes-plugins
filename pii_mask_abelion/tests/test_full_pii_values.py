import pytest
from pii_mask_abelion.pii_middleware import mask_content,pii_middleware
@pytest.mark.parametrize('text,sentinel',[
 ('email: CANARYPerson@example.invalid','@example.invalid'),
 ('Contact CANARYPerson@example.invalid for the fixture.','CANARYPerson@example.invalid'),
 ('phone: +6281234567890','+6281234567890'),
 ('Contact number +6281234567890 belongs to the fixture.','+6281234567890'),
])
def test_complete_pii_in_exported_stateless_helper(text,sentinel):
 masked,count=mask_content(text)
 assert sentinel not in masked and count>0
 request={'messages':[{'role':'user','content':text}]}
 result=pii_middleware(request)
 assert sentinel not in str(result['request'])
 assert request['messages'][0]['content']==text

def test_correct_shape_cloud_key_and_jwt_controls():
 from pii_mask_abelion.guard import Guard
 # Shape-only synthetic controls, never accepted by any service.
 for value in ['AKIA'+'Z9'*8,'eyJ'+'Z'*12+'.'+'a'*12+'.'+'b'*16]:
  assert value not in Guard().output(value,session_id='shape',platform='api')
