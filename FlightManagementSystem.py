import datetime
import os
import re
import asyncio
from typing import List
from prettytable import PrettyTable
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie, PydanticObjectId

# 从 DBC 获取 schema
from FlightDataBaseConnector import Flight, FlightDBC, BookingStatus


class FlightManagementSystem:
    def __init__(self):
        self.DBC = FlightDBC

    @staticmethod
    async def init_database() -> None:
        """初始化数据库
        """
        client = AsyncIOMotorClient('mongodb://localhost:27017')
        database = client['flight_db']
        await init_beanie(database=database, document_models=[Flight])

    async def add_flight(self) -> PydanticObjectId | None:
        """添加航班信息
        """
        flight_number = input("请输入航班号：")
        departure_time = input("请输入起飞时间（格式：yyyy-mm-dd HH:MM）：")
        origin = input("请输入出发地：")
        destination = input("请输入目的地：")
        estimated_arrival_time = input("请输入预计到达时间（格式：yyyy-mm-dd HH:MM）：")
        flight_size = input("请输入航班座位数量：")

        # 校验时间是否有效
        try:
            departure_time = datetime.datetime.strptime(departure_time, "%Y-%m-%d %H:%M")
            estimated_arrival_time = datetime.datetime.strptime(estimated_arrival_time, "%Y-%m-%d %H:%M")
            if departure_time >= estimated_arrival_time:
                print("错误：起飞时间应早于落地时间！")
                return
        except ValueError:
            print("错误：时间格式错误！")
            return

        # 检验座位数是否有效
        try:
            flight_size = int(flight_size)
        except ValueError as e:
            print("座位数量应为整数！")
            print(str(e))
            return

        # 创建航班
        return await self.DBC.add_flight(flight_number=flight_number, departure_time=departure_time, origin=origin,
                                         destination=destination, estimated_arrival_time=estimated_arrival_time,
                                         flight_size=flight_size)

    @staticmethod
    async def display_flights(flights: List[Flight]):
        """用表格美观显示航班信息
        """
        # 创建表格对象
        table = PrettyTable()
        table.field_names = [
            "No.", "FlightNumber", "DepartureTime", "Origin", "Destination", "EstimatedArrivalTime", "SeatsAvailable"
        ]

        # 遍历航班信息，添加到表格中
        for _id, flight in enumerate(flights):
            table.add_row([
                _id + 1,
                flight.flight_number,
                flight.departure_time.strftime("%Y-%m-%d %H:%M"),
                flight.origin,
                flight.destination,
                flight.estimated_arrival_time.strftime("%Y-%m-%d %H:%M"),
                f"{flight.seats_available}/{flight.seats_total}"
            ])

        # 输出表格
        print(table)

    async def show_all_flights(self):
        """查找并展示所有航班信息
        """
        await self.display_flights(await self.DBC.get_flights())

    async def display_flight(self, flight_id: PydanticObjectId | None):
        """显示特定航班信息"""
        if flight_id is None:
            return
        flight = await Flight.get(flight_id)
        await self.display_flights([flight])

        table = PrettyTable()
        table.field_names = [
            'SeatNumber', 'Status', 'PassengerName', 'PassengerId', 'BookingTime'
        ]

        for booking in flight.bookings:
            table.add_row([
                booking.seat_number,
                booking.booking_status.value,
                None if booking.passenger_name is None else booking.passenger_name,
                None if booking.passenger_id is None else booking.passenger_id,
                None if booking.booking_time is None else booking.booking_time.strftime("%Y-%m-%d %H:%M")
            ])

        # 输出表格
        print(table)

    async def find_flights(self) -> List[Flight] | None:
        """查找符合条件的所有航班"""
        await self.show_all_flights()

        print("请选择航班（以下选项没有要求直接换行即可）")
        flight_number = input("航班号：").strip()
        start_time_str = input("起飞时间应晚于(YYYY-MM-DD HH:MM): ").strip()
        start_time = None if start_time_str == "" else datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        end_time_str = input("起飞时间应早于 (YYYY-MM-DD HH:MM): ").strip()
        end_time = None if end_time_str == "" else datetime.datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
        origin = input("出发地: ").strip()
        destination = input("目的地: ").strip()

        flights = await self.DBC.get_flights(
            flight_number=flight_number,
            origin=origin,
            destination=destination,
            start_time=start_time,
            end_time=end_time
        )
        if len(flights) == 0:
            print("暂无符合条件的航班！")
            return None
        await self.display_flights(flights)
        return flights

    @staticmethod
    async def select_flight(flights) -> PydanticObjectId | None:
        """选择特定的航班"""
        if flights is None:
            return None
        number = int(re.sub(r'\D', '', input("请输入想要选择的航班序号（输入0退出）：")))
        if number == 0:
            return None
        if not 1 <= number <= len(flights):
            print("输入数字有误，超出可选范围！")
            return
        print(f"成功选择航班：{flights[number - 1].flight_number}")
        return flights[number - 1].id

    async def book_flight(self, status: BookingStatus):
        """预定/取消预定航班"""
        flight_id = await self.select_flight(await self.find_flights())
        if flight_id is None:
            return None
        await self.display_flight(flight_id=flight_id)
        seat_number = input("座位号：").strip()
        passenger_name = input("乘客姓名：").strip()
        passenger_id = input("乘客身份证号：").strip()
        await self.DBC.book_flight(flight_id=flight_id, seat_number=seat_number, passenger_name=passenger_name,
                                   passenger_id=passenger_id, status=status)
        await self.display_flight(flight_id=flight_id)

    async def run(self):
        """运行系统"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("""
    > 航班管理系统 < 
    >  MattWong  <
""")
        while True:
            choice = input("""
系统功能：
输入 1：添加航班
输入 2：查找航班
输入 3：预定航班
输入 4：取消预定航班
输入 0：退出系统
""")
            # 去除非数字字符
            choice = int(re.sub(r'\D', '', choice))
            match choice:
                case 1:
                    await self.add_flight()
                case 2:
                    await self.display_flight(await self.select_flight(await self.find_flights()))
                case 3:
                    await self.book_flight(BookingStatus.BOOKED)
                case 4:
                    await self.book_flight(BookingStatus.AVAILABLE)
                case 0:
                    print("退出程序！")
                    return
                case _:
                    print("输入错误,请重新输入...")


async def main():
    FMS = FlightManagementSystem()
    await FMS.init_database()
    await FMS.run()

    # 清空数据库
    # await Flight.delete_all()


if __name__ == '__main__':
    asyncio.run(main())
