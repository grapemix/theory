# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: theory.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2
from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='theory.proto',
  package='theory',
  syntax='proto3',
  serialized_pb=_b('\n\x0ctheory.proto\x12\x06theory\x1a\x19google/protobuf/any.proto\x1a\x1bgoogle/protobuf/empty.proto\"4\n\x05UiReq\x12\x0e\n\x06\x61\x63tion\x18\x01 \x01(\t\x12\x0b\n\x03val\x18\x02 \x01(\t\x12\x0e\n\x06userId\x18\x03 \x01(\t\")\n\nReactorReq\x12\x0e\n\x06\x61\x63tion\x18\x01 \x01(\t\x12\x0b\n\x03val\x18\x02 \x01(\t\"3\n\rReactorReqArr\x12\"\n\x06reqLst\x18\x01 \x03(\x0b\x32\x12.theory.ReactorReq\"&\n\x04UiId\x12\n\n\x02id\x18\x01 \x01(\t\x12\x12\n\nadapterLst\x18\x02 \x03(\t\"Q\n\tFieldData\x12\r\n\x05\x63mdId\x18\x01 \x01(\x05\x12\x10\n\x08\x66ormHash\x18\x02 \x01(\t\x12\x11\n\tfieldName\x18\x03 \x01(\t\x12\x10\n\x08jsonData\x18\x04 \x01(\t\"Q\n\x0b\x43mdFxnInput\x12\r\n\x05\x63mdId\x18\x01 \x01(\x05\x12\x10\n\x08\x66ormHash\x18\x02 \x01(\t\x12\x0f\n\x07\x66xnName\x18\x03 \x01(\t\x12\x10\n\x08jsonData\x18\x04 \x01(\t\"@\n\x0euiData4Adapter\x12\x1c\n\x14\x61\x64\x61pterBufferModelId\x18\x01 \x01(\x05\x12\x10\n\x08jsonData\x18\x02 \x01(\t\"\x1c\n\x08JsonData\x12\x10\n\x08jsonData\x18\x01 \x01(\t\"+\n\x07MdlIden\x12\x0f\n\x07\x61ppName\x18\x01 \x01(\t\x12\x0f\n\x07mdlName\x18\x02 \x01(\t\"^\n\tMdlTblReq\x12\x1c\n\x03mdl\x18\x01 \x01(\x0b\x32\x0f.theory.MdlIden\x12\x0f\n\x07pageNum\x18\x02 \x01(\x05\x12\x10\n\x08pageSize\x18\x03 \x01(\x05\x12\x10\n\x08\x66ormHash\x18\x04 \x01(\t\"j\n\x03Mdl\x12!\n\x03mdl\x18\x01 \x03(\x0b\x32\x14.theory.Mdl.MdlEntry\x1a@\n\x08MdlEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12#\n\x05value\x18\x02 \x01(\x0b\x32\x14.google.protobuf.Any:\x02\x38\x01\"?\n\x11MultiModelLstData\x12*\n\x0cmodelLstData\x18\x01 \x03(\x0b\x32\x14.theory.ModelLstData\"E\n\x0cModelLstData\x12\x0f\n\x07\x61ppName\x18\x01 \x01(\t\x12\x0f\n\x07mdlName\x18\x02 \x01(\t\x12\x13\n\x0bjsonDataLst\x18\x03 \x03(\t\"c\n\x08StrVsMap\x12\t\n\x01k\x18\x01 \x01(\t\x12\"\n\x01v\x18\x02 \x03(\x0b\x32\x17.theory.StrVsMap.VEntry\x1a(\n\x06VEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\"\x18\n\x06StrLst\x12\x0e\n\x06strLst\x18\x01 \x03(\t\"\x18\n\x06IntLst\x12\x0e\n\x06intLst\x18\x01 \x03(\x05\"\x17\n\x07\x44\x61taRow\x12\x0c\n\x04\x63\x65ll\x18\x01 \x03(\t\"\x8a\x01\n\x0fSpreadSheetData\x12 \n\x07\x64\x61taLst\x18\x01 \x03(\x0b\x32\x0f.theory.DataRow\x12)\n\x0f\x66ieldNameVsProp\x18\x02 \x03(\x0b\x32\x10.theory.StrVsMap\x12\x13\n\x0bmdlTotalNum\x18\x03 \x01(\x05\x12\x15\n\rspreadSheetId\x18\x04 \x01(\x05\"\x07\n\x05\x45mpty2\xc9\x03\n\x07Reactor\x12.\n\x03\x62ye\x12\r.theory.Empty\x1a\x16.google.protobuf.Empty\"\x00\x12.\n\x04\x63\x61ll\x12\r.theory.UiReq\x1a\x15.theory.ReactorReqArr\"\x00\x12\x31\n\x08register\x12\x0c.theory.UiId\x1a\x15.theory.ReactorReqArr\"\x00\x12\x35\n\x0csyncFormData\x12\x11.theory.FieldData\x1a\x10.theory.JsonData\"\x00\x12\x38\n\rcallCmdSubFxn\x12\x13.theory.CmdFxnInput\x1a\x10.theory.JsonData\"\x00\x12\x39\n\x0b\x61\x64\x61ptFromUi\x12\x16.theory.uiData4Adapter\x1a\x10.theory.JsonData\"\x00\x12\x44\n\x0eupsertModelLst\x12\x19.theory.MultiModelLstData\x1a\x15.theory.ReactorReqArr\"\x00\x12\x39\n\tgetMdlTbl\x12\x11.theory.MdlTblReq\x1a\x17.theory.SpreadSheetData\"\x00\x62\x06proto3')
  ,
  dependencies=[google_dot_protobuf_dot_any__pb2.DESCRIPTOR,google_dot_protobuf_dot_empty__pb2.DESCRIPTOR,])




_UIREQ = _descriptor.Descriptor(
  name='UiReq',
  full_name='theory.UiReq',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='action', full_name='theory.UiReq.action', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='val', full_name='theory.UiReq.val', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='userId', full_name='theory.UiReq.userId', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=80,
  serialized_end=132,
)


_REACTORREQ = _descriptor.Descriptor(
  name='ReactorReq',
  full_name='theory.ReactorReq',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='action', full_name='theory.ReactorReq.action', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='val', full_name='theory.ReactorReq.val', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=134,
  serialized_end=175,
)


_REACTORREQARR = _descriptor.Descriptor(
  name='ReactorReqArr',
  full_name='theory.ReactorReqArr',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='reqLst', full_name='theory.ReactorReqArr.reqLst', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=177,
  serialized_end=228,
)


_UIID = _descriptor.Descriptor(
  name='UiId',
  full_name='theory.UiId',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='theory.UiId.id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='adapterLst', full_name='theory.UiId.adapterLst', index=1,
      number=2, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=230,
  serialized_end=268,
)


_FIELDDATA = _descriptor.Descriptor(
  name='FieldData',
  full_name='theory.FieldData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='cmdId', full_name='theory.FieldData.cmdId', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='formHash', full_name='theory.FieldData.formHash', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='fieldName', full_name='theory.FieldData.fieldName', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='jsonData', full_name='theory.FieldData.jsonData', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=270,
  serialized_end=351,
)


_CMDFXNINPUT = _descriptor.Descriptor(
  name='CmdFxnInput',
  full_name='theory.CmdFxnInput',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='cmdId', full_name='theory.CmdFxnInput.cmdId', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='formHash', full_name='theory.CmdFxnInput.formHash', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='fxnName', full_name='theory.CmdFxnInput.fxnName', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='jsonData', full_name='theory.CmdFxnInput.jsonData', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=353,
  serialized_end=434,
)


_UIDATA4ADAPTER = _descriptor.Descriptor(
  name='uiData4Adapter',
  full_name='theory.uiData4Adapter',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='adapterBufferModelId', full_name='theory.uiData4Adapter.adapterBufferModelId', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='jsonData', full_name='theory.uiData4Adapter.jsonData', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=436,
  serialized_end=500,
)


_JSONDATA = _descriptor.Descriptor(
  name='JsonData',
  full_name='theory.JsonData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='jsonData', full_name='theory.JsonData.jsonData', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=502,
  serialized_end=530,
)


_MDLIDEN = _descriptor.Descriptor(
  name='MdlIden',
  full_name='theory.MdlIden',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='appName', full_name='theory.MdlIden.appName', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mdlName', full_name='theory.MdlIden.mdlName', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=532,
  serialized_end=575,
)


_MDLTBLREQ = _descriptor.Descriptor(
  name='MdlTblReq',
  full_name='theory.MdlTblReq',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='mdl', full_name='theory.MdlTblReq.mdl', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='pageNum', full_name='theory.MdlTblReq.pageNum', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='pageSize', full_name='theory.MdlTblReq.pageSize', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='formHash', full_name='theory.MdlTblReq.formHash', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=577,
  serialized_end=671,
)


_MDL_MDLENTRY = _descriptor.Descriptor(
  name='MdlEntry',
  full_name='theory.Mdl.MdlEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='key', full_name='theory.Mdl.MdlEntry.key', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='value', full_name='theory.Mdl.MdlEntry.value', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=_descriptor._ParseOptions(descriptor_pb2.MessageOptions(), _b('8\001')),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=715,
  serialized_end=779,
)

_MDL = _descriptor.Descriptor(
  name='Mdl',
  full_name='theory.Mdl',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='mdl', full_name='theory.Mdl.mdl', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_MDL_MDLENTRY, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=673,
  serialized_end=779,
)


_MULTIMODELLSTDATA = _descriptor.Descriptor(
  name='MultiModelLstData',
  full_name='theory.MultiModelLstData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='modelLstData', full_name='theory.MultiModelLstData.modelLstData', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=781,
  serialized_end=844,
)


_MODELLSTDATA = _descriptor.Descriptor(
  name='ModelLstData',
  full_name='theory.ModelLstData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='appName', full_name='theory.ModelLstData.appName', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mdlName', full_name='theory.ModelLstData.mdlName', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='jsonDataLst', full_name='theory.ModelLstData.jsonDataLst', index=2,
      number=3, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=846,
  serialized_end=915,
)


_STRVSMAP_VENTRY = _descriptor.Descriptor(
  name='VEntry',
  full_name='theory.StrVsMap.VEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='key', full_name='theory.StrVsMap.VEntry.key', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='value', full_name='theory.StrVsMap.VEntry.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=_descriptor._ParseOptions(descriptor_pb2.MessageOptions(), _b('8\001')),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=976,
  serialized_end=1016,
)

_STRVSMAP = _descriptor.Descriptor(
  name='StrVsMap',
  full_name='theory.StrVsMap',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='k', full_name='theory.StrVsMap.k', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='v', full_name='theory.StrVsMap.v', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[_STRVSMAP_VENTRY, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=917,
  serialized_end=1016,
)


_STRLST = _descriptor.Descriptor(
  name='StrLst',
  full_name='theory.StrLst',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='strLst', full_name='theory.StrLst.strLst', index=0,
      number=1, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1018,
  serialized_end=1042,
)


_INTLST = _descriptor.Descriptor(
  name='IntLst',
  full_name='theory.IntLst',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='intLst', full_name='theory.IntLst.intLst', index=0,
      number=1, type=5, cpp_type=1, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1044,
  serialized_end=1068,
)


_DATAROW = _descriptor.Descriptor(
  name='DataRow',
  full_name='theory.DataRow',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='cell', full_name='theory.DataRow.cell', index=0,
      number=1, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1070,
  serialized_end=1093,
)


_SPREADSHEETDATA = _descriptor.Descriptor(
  name='SpreadSheetData',
  full_name='theory.SpreadSheetData',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='dataLst', full_name='theory.SpreadSheetData.dataLst', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='fieldNameVsProp', full_name='theory.SpreadSheetData.fieldNameVsProp', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='mdlTotalNum', full_name='theory.SpreadSheetData.mdlTotalNum', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='spreadSheetId', full_name='theory.SpreadSheetData.spreadSheetId', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1096,
  serialized_end=1234,
)


_EMPTY = _descriptor.Descriptor(
  name='Empty',
  full_name='theory.Empty',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1236,
  serialized_end=1243,
)

_REACTORREQARR.fields_by_name['reqLst'].message_type = _REACTORREQ
_MDLTBLREQ.fields_by_name['mdl'].message_type = _MDLIDEN
_MDL_MDLENTRY.fields_by_name['value'].message_type = google_dot_protobuf_dot_any__pb2._ANY
_MDL_MDLENTRY.containing_type = _MDL
_MDL.fields_by_name['mdl'].message_type = _MDL_MDLENTRY
_MULTIMODELLSTDATA.fields_by_name['modelLstData'].message_type = _MODELLSTDATA
_STRVSMAP_VENTRY.containing_type = _STRVSMAP
_STRVSMAP.fields_by_name['v'].message_type = _STRVSMAP_VENTRY
_SPREADSHEETDATA.fields_by_name['dataLst'].message_type = _DATAROW
_SPREADSHEETDATA.fields_by_name['fieldNameVsProp'].message_type = _STRVSMAP
DESCRIPTOR.message_types_by_name['UiReq'] = _UIREQ
DESCRIPTOR.message_types_by_name['ReactorReq'] = _REACTORREQ
DESCRIPTOR.message_types_by_name['ReactorReqArr'] = _REACTORREQARR
DESCRIPTOR.message_types_by_name['UiId'] = _UIID
DESCRIPTOR.message_types_by_name['FieldData'] = _FIELDDATA
DESCRIPTOR.message_types_by_name['CmdFxnInput'] = _CMDFXNINPUT
DESCRIPTOR.message_types_by_name['uiData4Adapter'] = _UIDATA4ADAPTER
DESCRIPTOR.message_types_by_name['JsonData'] = _JSONDATA
DESCRIPTOR.message_types_by_name['MdlIden'] = _MDLIDEN
DESCRIPTOR.message_types_by_name['MdlTblReq'] = _MDLTBLREQ
DESCRIPTOR.message_types_by_name['Mdl'] = _MDL
DESCRIPTOR.message_types_by_name['MultiModelLstData'] = _MULTIMODELLSTDATA
DESCRIPTOR.message_types_by_name['ModelLstData'] = _MODELLSTDATA
DESCRIPTOR.message_types_by_name['StrVsMap'] = _STRVSMAP
DESCRIPTOR.message_types_by_name['StrLst'] = _STRLST
DESCRIPTOR.message_types_by_name['IntLst'] = _INTLST
DESCRIPTOR.message_types_by_name['DataRow'] = _DATAROW
DESCRIPTOR.message_types_by_name['SpreadSheetData'] = _SPREADSHEETDATA
DESCRIPTOR.message_types_by_name['Empty'] = _EMPTY
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

UiReq = _reflection.GeneratedProtocolMessageType('UiReq', (_message.Message,), dict(
  DESCRIPTOR = _UIREQ,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.UiReq)
  ))
_sym_db.RegisterMessage(UiReq)

ReactorReq = _reflection.GeneratedProtocolMessageType('ReactorReq', (_message.Message,), dict(
  DESCRIPTOR = _REACTORREQ,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.ReactorReq)
  ))
_sym_db.RegisterMessage(ReactorReq)

ReactorReqArr = _reflection.GeneratedProtocolMessageType('ReactorReqArr', (_message.Message,), dict(
  DESCRIPTOR = _REACTORREQARR,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.ReactorReqArr)
  ))
_sym_db.RegisterMessage(ReactorReqArr)

UiId = _reflection.GeneratedProtocolMessageType('UiId', (_message.Message,), dict(
  DESCRIPTOR = _UIID,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.UiId)
  ))
_sym_db.RegisterMessage(UiId)

FieldData = _reflection.GeneratedProtocolMessageType('FieldData', (_message.Message,), dict(
  DESCRIPTOR = _FIELDDATA,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.FieldData)
  ))
_sym_db.RegisterMessage(FieldData)

CmdFxnInput = _reflection.GeneratedProtocolMessageType('CmdFxnInput', (_message.Message,), dict(
  DESCRIPTOR = _CMDFXNINPUT,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.CmdFxnInput)
  ))
_sym_db.RegisterMessage(CmdFxnInput)

uiData4Adapter = _reflection.GeneratedProtocolMessageType('uiData4Adapter', (_message.Message,), dict(
  DESCRIPTOR = _UIDATA4ADAPTER,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.uiData4Adapter)
  ))
_sym_db.RegisterMessage(uiData4Adapter)

JsonData = _reflection.GeneratedProtocolMessageType('JsonData', (_message.Message,), dict(
  DESCRIPTOR = _JSONDATA,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.JsonData)
  ))
_sym_db.RegisterMessage(JsonData)

MdlIden = _reflection.GeneratedProtocolMessageType('MdlIden', (_message.Message,), dict(
  DESCRIPTOR = _MDLIDEN,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.MdlIden)
  ))
_sym_db.RegisterMessage(MdlIden)

MdlTblReq = _reflection.GeneratedProtocolMessageType('MdlTblReq', (_message.Message,), dict(
  DESCRIPTOR = _MDLTBLREQ,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.MdlTblReq)
  ))
_sym_db.RegisterMessage(MdlTblReq)

Mdl = _reflection.GeneratedProtocolMessageType('Mdl', (_message.Message,), dict(

  MdlEntry = _reflection.GeneratedProtocolMessageType('MdlEntry', (_message.Message,), dict(
    DESCRIPTOR = _MDL_MDLENTRY,
    __module__ = 'theory_pb2'
    # @@protoc_insertion_point(class_scope:theory.Mdl.MdlEntry)
    ))
  ,
  DESCRIPTOR = _MDL,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.Mdl)
  ))
_sym_db.RegisterMessage(Mdl)
_sym_db.RegisterMessage(Mdl.MdlEntry)

MultiModelLstData = _reflection.GeneratedProtocolMessageType('MultiModelLstData', (_message.Message,), dict(
  DESCRIPTOR = _MULTIMODELLSTDATA,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.MultiModelLstData)
  ))
_sym_db.RegisterMessage(MultiModelLstData)

ModelLstData = _reflection.GeneratedProtocolMessageType('ModelLstData', (_message.Message,), dict(
  DESCRIPTOR = _MODELLSTDATA,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.ModelLstData)
  ))
_sym_db.RegisterMessage(ModelLstData)

StrVsMap = _reflection.GeneratedProtocolMessageType('StrVsMap', (_message.Message,), dict(

  VEntry = _reflection.GeneratedProtocolMessageType('VEntry', (_message.Message,), dict(
    DESCRIPTOR = _STRVSMAP_VENTRY,
    __module__ = 'theory_pb2'
    # @@protoc_insertion_point(class_scope:theory.StrVsMap.VEntry)
    ))
  ,
  DESCRIPTOR = _STRVSMAP,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.StrVsMap)
  ))
_sym_db.RegisterMessage(StrVsMap)
_sym_db.RegisterMessage(StrVsMap.VEntry)

StrLst = _reflection.GeneratedProtocolMessageType('StrLst', (_message.Message,), dict(
  DESCRIPTOR = _STRLST,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.StrLst)
  ))
_sym_db.RegisterMessage(StrLst)

IntLst = _reflection.GeneratedProtocolMessageType('IntLst', (_message.Message,), dict(
  DESCRIPTOR = _INTLST,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.IntLst)
  ))
_sym_db.RegisterMessage(IntLst)

DataRow = _reflection.GeneratedProtocolMessageType('DataRow', (_message.Message,), dict(
  DESCRIPTOR = _DATAROW,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.DataRow)
  ))
_sym_db.RegisterMessage(DataRow)

SpreadSheetData = _reflection.GeneratedProtocolMessageType('SpreadSheetData', (_message.Message,), dict(
  DESCRIPTOR = _SPREADSHEETDATA,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.SpreadSheetData)
  ))
_sym_db.RegisterMessage(SpreadSheetData)

Empty = _reflection.GeneratedProtocolMessageType('Empty', (_message.Message,), dict(
  DESCRIPTOR = _EMPTY,
  __module__ = 'theory_pb2'
  # @@protoc_insertion_point(class_scope:theory.Empty)
  ))
_sym_db.RegisterMessage(Empty)


_MDL_MDLENTRY.has_options = True
_MDL_MDLENTRY._options = _descriptor._ParseOptions(descriptor_pb2.MessageOptions(), _b('8\001'))
_STRVSMAP_VENTRY.has_options = True
_STRVSMAP_VENTRY._options = _descriptor._ParseOptions(descriptor_pb2.MessageOptions(), _b('8\001'))

_REACTOR = _descriptor.ServiceDescriptor(
  name='Reactor',
  full_name='theory.Reactor',
  file=DESCRIPTOR,
  index=0,
  options=None,
  serialized_start=1246,
  serialized_end=1703,
  methods=[
  _descriptor.MethodDescriptor(
    name='bye',
    full_name='theory.Reactor.bye',
    index=0,
    containing_service=None,
    input_type=_EMPTY,
    output_type=google_dot_protobuf_dot_empty__pb2._EMPTY,
    options=None,
  ),
  _descriptor.MethodDescriptor(
    name='call',
    full_name='theory.Reactor.call',
    index=1,
    containing_service=None,
    input_type=_UIREQ,
    output_type=_REACTORREQARR,
    options=None,
  ),
  _descriptor.MethodDescriptor(
    name='register',
    full_name='theory.Reactor.register',
    index=2,
    containing_service=None,
    input_type=_UIID,
    output_type=_REACTORREQARR,
    options=None,
  ),
  _descriptor.MethodDescriptor(
    name='syncFormData',
    full_name='theory.Reactor.syncFormData',
    index=3,
    containing_service=None,
    input_type=_FIELDDATA,
    output_type=_JSONDATA,
    options=None,
  ),
  _descriptor.MethodDescriptor(
    name='callCmdSubFxn',
    full_name='theory.Reactor.callCmdSubFxn',
    index=4,
    containing_service=None,
    input_type=_CMDFXNINPUT,
    output_type=_JSONDATA,
    options=None,
  ),
  _descriptor.MethodDescriptor(
    name='adaptFromUi',
    full_name='theory.Reactor.adaptFromUi',
    index=5,
    containing_service=None,
    input_type=_UIDATA4ADAPTER,
    output_type=_JSONDATA,
    options=None,
  ),
  _descriptor.MethodDescriptor(
    name='upsertModelLst',
    full_name='theory.Reactor.upsertModelLst',
    index=6,
    containing_service=None,
    input_type=_MULTIMODELLSTDATA,
    output_type=_REACTORREQARR,
    options=None,
  ),
  _descriptor.MethodDescriptor(
    name='getMdlTbl',
    full_name='theory.Reactor.getMdlTbl',
    index=7,
    containing_service=None,
    input_type=_MDLTBLREQ,
    output_type=_SPREADSHEETDATA,
    options=None,
  ),
])
_sym_db.RegisterServiceDescriptor(_REACTOR)

DESCRIPTOR.services_by_name['Reactor'] = _REACTOR

# @@protoc_insertion_point(module_scope)
