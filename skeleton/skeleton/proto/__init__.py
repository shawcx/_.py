
from . import Skeleton_pb2

@_.records.protobuf.handle(Skeleton_pb2.NoTable)
class CustomNoTable:
    async def get(self, record_id=None):
        self.write(f'hello {record_id}')
