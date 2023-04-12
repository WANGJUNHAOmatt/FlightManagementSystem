import datetime
from typing import List
from enum import StrEnum, auto
from pydantic import BaseModel, validator
from beanie import Document, PydanticObjectId


class BookingStatus(StrEnum):
    """座位预定状态"""
    AVAILABLE = auto()
    BOOKED = auto()


class Booking(BaseModel):
    """座位预定信息"""
    seat_number: str = None
    booking_status: BookingStatus = None
    passenger_name: str = None
    passenger_id: str = None
    booking_time: datetime.datetime = None


class Flight(Document):
    """航班信息"""
    flight_number: str = None
    departure_time: datetime.datetime = None
    origin: str = None
    destination: str = None
    estimated_arrival_time: datetime.datetime = None
    seats_total: int = None
    seats_available: int = None
    bookings: List[Booking] = None

    @validator("estimated_arrival_time")
    def validate_arrival_time(cls, v, values):
        if "departure_time" in values and v <= values["departure_time"]:
            raise ValueError("estimated_arrival_time should be later than departure_time")
        return v


class FlightDBC:
    """DatabaseConnector for flight"""

    @staticmethod
    async def add_flight(
            flight_number: str, departure_time: datetime.datetime, origin: str, destination: str,
            estimated_arrival_time: datetime.datetime,
            flight_size: int) -> PydanticObjectId:
        """添加一条航班信息到数据库"""
        # 创建航班对象
        flight = Flight(
            flight_number=flight_number,
            departure_time=departure_time,
            origin=origin,
            destination=destination,
            estimated_arrival_time=estimated_arrival_time,
            seats_total=flight_size,
            seats_available=flight_size,
            bookings=[]
        )
        # 添加座位信息
        for i in range(flight_size):
            seat_number = i + 1
            booking_status = "available"
            passenger_name = None
            passenger_id = None
            booking_time = None

            # 创建座位对象
            booking = Booking(
                seat_number=seat_number,
                booking_status=booking_status,
                passenger_name=passenger_name,
                passenger_id=passenger_id,
                booking_time=booking_time
            )

            # 添加座位对象到航班对象中
            flight.bookings.append(booking)

        # 保存航班对象到数据库中
        await flight.save()
        print("航班信息已保存！")
        # 返回 PydanticObjectId
        return flight.id

    @staticmethod
    async def get_flights(flight_number: str = None, origin: str = None, destination: str = None,
                          start_time: datetime.datetime = None, end_time: datetime.datetime = None
                          ) -> List[Flight]:
        """查找符合条件的所有航班信息"""
        # 构造查询条件
        query = {}

        if flight_number:
            query["flight_number"] = flight_number

        if origin:
            query["origin"] = origin

        if destination:
            query["destination"] = destination

        if start_time:
            query["departure_time"] = {
                "$gte": start_time
            }

        if end_time:
            query["departure_time__lt"] = {
                "$lt": end_time
            }

        # 获取所有符合条件到航班信息
        flights = await Flight.find(query).to_list()
        return flights

    @staticmethod
    async def book_flight(
            flight_id: PydanticObjectId,
            seat_number: str,
            passenger_name: str,
            passenger_id: str,
            status: BookingStatus
    ) -> None:
        """预定或取消预定座位"""
        # 查询航班信息
        flight = await Flight.get(flight_id)

        if not flight:
            print(f"航班不存在")
            return

        # 查询座位信息
        for booking in flight.bookings:
            if booking.seat_number == seat_number:
                if booking.booking_status == status:
                    print(f"ERROR：座位 {seat_number} {'已' if status == BookingStatus.BOOKED else '未'}被预订")
                    return
                # 校验退订人 是否 和 预定人身份是否一致
                if status == BookingStatus.AVAILABLE:
                    if booking.passenger_id != passenger_id or booking.passenger_name != passenger_name:
                        print(f"ERROR：身份信息不符合，无法退订！")
                        return
                # 更新 booking 信息
                booking.passenger_name = None if status == BookingStatus.AVAILABLE else passenger_name
                booking.passenger_id = None if status == BookingStatus.AVAILABLE else passenger_id
                booking.booking_status = status
                booking.booking_time = None if status == BookingStatus.AVAILABLE else datetime.datetime.utcnow()

                flight.seats_available += -1 if status == BookingStatus.BOOKED else 1
                await flight.save()
                print(f"座位 {seat_number} {'取消' if status == BookingStatus.AVAILABLE else ''} 预订成功")
                return

        print("座位号错误！预定失败")
