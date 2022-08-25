import multiprocessing
import backtrader as bt
from . import util
import backtrader.feeds as btfeeds
import backtrader.indicators as btind
import pandas as pd

# data_value_list  = None #essential
trade_result = None# essential
hold_result  = None#essential

class SmaAverages(bt.Strategy):
    params = (
        ('period_sma10', 10),
        ('period_sma30', 30),
        ('stakesize',0)
    )

    # 打印日志
    def log(self, txt, dt=None):

        dt = dt or self.data.datetime.date(0)

        # print('%s, %s' % (dt, txt))

    def __init__(self):

        # 用于保存订单
        self.order = None
        # 订单价格
        self.buyprice = None
        # 订单佣金
        self.buycomm = None

        self.sma10=dict()
        self.sma30=dict()
        for data in self.datas:
        # 计算10日均线
         self.sma10[data._name] = btind.MovingAverageSimple(data.close, period=self.params.period_sma10)
        # 计算30日均线
         self.sma30[data._name] = btind.MovingAverageSimple(data.close, period=self.params.period_sma30)

    def notify_order(self, order):


        # 等待订单提交、订单被cerebro接受
        if order.status in [order.Submitted, order.Accepted]:
            return

        # 等待订单完成
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))



            else:
                self.log(
                    'SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))

        # 如果订单保证金不足，将不会完成，而是执行以下拒绝程序
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def notify_trade(self, trade):

        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))  # pnl：盈利  pnlcomm：手续费

    # 策略逻辑实现
    def next(self):

     for data in self.datas:
        pos = self.getposition(data)
        # 当今天的10日均线大于30日均线并且昨天的10日均线小于30日均线，则进入市场（买）
        if pos.size==0:
         if self.sma10[data._name][0] > self.sma30[data._name][0] and self.sma10[data._name][-1] < self.sma30[data._name][-1]:
            # 判断订单是否完成，完成则为None，否则为订单信息
            if self.order:
                return

            # 若上一个订单处理完成，可继续执行买入操作
            self.params.stakesize = int(self.broker.getcash()/data.close*0.4)
            self.order = self.buy(data=data,size=self.params.stakesize)
            #保存每轮交易列表,essential
            temp = util.return_trade_dict(data,"buy",self.params.stakesize)
            global trade_result
            trade_result = pd.concat([temp, trade_result])

        # 当今天的10日均线小于30日均线并且昨天的10日均线大于30日均线，则退出市场（卖）

        elif pos.size>0: #essential,必须要判断此股票是否持仓，如果持仓才能卖

          if self.sma10[data._name][0] < self.sma30[data._name][0] and self.sma10[data._name][-1] > self.sma30[data._name][-1]:
            # 卖出
            self.params.stakesize = 5000
            if(pos.size-self.params.stakesize>=0): #即将卖出的数量是大于持仓数量
                self.order = self.sell(data=data,size=self.params.stakesize)
                #保存每轮的交易列表,essential
                temp=util.return_trade_dict(data,"sell",self.params.stakesize)
                trade_result = pd.concat([temp, trade_result])
            else:  #如果不大于，则直接清仓，而不是使用上面即将想卖出的数量
                self.params.stakesize=pos.size
                self.order = self.sell(data=data, size=self.params.stakesize)
                #保存每轮交易列表,essential
                temp=util.return_trade_dict(data,"sell",self.params.stakesize)
                trade_result = pd.concat([temp, trade_result])

     # 每轮买卖结束后，看持仓的股票,essential
     for data in self.datas:

         pos = self.getposition(data)

         if len(pos):
               # 存持仓列表
               temp=util.return_hold_dict(pos,data)
               global hold_result
               hold_result = pd.concat([temp, hold_result])
     # 保存每天的账户价值,essential
     util.date_value_list.append((self.data.datetime.date(0),self.broker.getvalue()))

def run_sma(ts_code_list, startdate, enddate):
    cerebro=bt.Cerebro()
    cerebro.addstrategy(SmaAverages)
    for ts_code in ts_code_list:
        stock=util.getdata(ts_code)
        start_year = int(startdate[0:4])
        start_month = int(startdate[4:6])
        start_day = int(startdate[6:8])
        end_year = int(enddate[0:4])
        end_month = int(enddate[4:6])
        end_day = int(enddate[6:8])
        data=btfeeds.PandasData(dataname=stock,fromdate=util.datetime.date(start_year,start_month,start_day),todate=util.datetime.date(end_year,end_month,end_day))
        cerebro.adddata(data,name=ts_code)
    cerebro.broker.setcash(1000000)
    cerebro.broker.setcommission(commission=0.001)
    util.add_custom_analyzer(cerebro)
    result=cerebro.run()
    strat=result[0]
    indicator_list=[cerebro.broker.getvalue()]
    indicator_list=util.return_indicators_list(strat,indicator_list)

    value_ratio = []
    value_ratio=util.calculate_date_profit(value_ratio,util.date_value_list)#计算每天的策略收益
    # hold_result:每日持仓&收益datafram
    # trade_result:交易详情datefram
    # value_ratio:每日策略收益,用来画折线图list
    # indicator_list:一号元素表示剩余持仓价值，二号元素表示复合收益总额,三号元素表示百分数表示年化收益率，
    # 四号元素表示最大回撤率，五号元素表示最大回撤金额,六号元素年化夏普比率list
    return hold_result.sort_values('date'),trade_result.sort_values('date'),value_ratio,indicator_list


    



