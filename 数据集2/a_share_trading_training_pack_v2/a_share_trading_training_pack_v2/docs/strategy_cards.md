# 策略卡片


## auction_feature

- **AUCTION_004 / 竞价红绿柱含义**：下档红柱代表挂买单多，绿柱代表挂卖单多；上档倒挂红柱代表买单未匹配，绿柱代表卖单未匹配。输出：`WAIT_CONFIRMATION`，风险：`low`。

## auction_rule

- **AUCTION_001 / 集合竞价9:15-9:20可挂可撤**：9:15-9:20挂单可撤，警惕诱多大单撤单。输出：`WAIT_CONFIRMATION`，风险：`low`。
- **AUCTION_002 / 集合竞价9:20-9:25只能挂不能撤**：9:20-9:25只能挂单不接受撤单。输出：`WAIT_CONFIRMATION`，风险：`low`。
- **AUCTION_003 / 集合竞价9:25-9:30不能挂不能撤**：9:25-9:30不能挂单也不能撤单。输出：`WAIT_CONFIRMATION`，风险：`low`。

## auction_shape

- **AUCTION_005 / 温和竞价跟踪**：温和集合竞价品种可重点关注盘中成交量及波动形态。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **AUCTION_006 / 诱空竞价跟踪**：诱空竞价品种可作为短线重点跟踪对象。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。

## auction_tail

- **AUCTION_007 / 竞价翘尾/踩尾**：竞价翘尾代表多头抢筹，竞价踩尾代表空头抛售。输出：`WAIT_CONFIRMATION`，风险：`medium`。

## chip_peak_pattern

- **CHIP_001 / 上峰不移，下跌不止**：上方套牢筹码峰未充分下移，下跌趋势中反弹到密集峰下沿易遇阻。输出：`AVOID_OR_WAIT`，风险：`medium`。
- **CHIP_002 / 单峰密集，主力参与**：低位长期整理形成单峰密集，放量突破单峰密集，通常是上升征兆。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **CHIP_003 / 筹码密集低位向下破位**：低位密集后向下破位，自由落体下跌，说明承接不足。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **CHIP_004 / 筹码密集低位向上突破**：低位密集后放量上穿，显示吸筹充分。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **CHIP_005 / 筹码密集高位向下破位**：高位密集后下破，通常为出货后下跌。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **CHIP_006 / 筹码密集高位继续上破**：高位密集后继续上破，可能为大盘未完或二次拉升出货准备。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **CHIP_007 / 下峰锁定，上涨未尽**：脱离低位筹码峰后，下方筹码未随上涨转移，表示主力未派发完。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **CHIP_008 / 双峰添谷，高抛低吸**：上下两个密集峰，股价在峰谷间震荡，峰谷逐步填满后等待方向突破。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **CHIP_009 / 多峰林立，行情延续**：拉升途中形成一个或多个筹码峰，代表持续进场推高，行情延续。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **CHIP_010 / 多峰锁仓，顶级强庄**：主升浪中连续拉升不放巨量，小山峰筹码，主力锁仓高控盘。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **CHIP_011 / 下消上移，换庄接力**：连续拉升后平台震荡，下方筹码上移，视作新主力接力。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **CHIP_012 / 多峰齐消，就是要逃**：下方筹码峰和顶格筹码同时消失，主力争先抛售，后续连续下跌。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **CHIP_013 / 顶格在消，强庄在逃**：顶格筹码消失松动，代表强庄抛售筹码。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## chip_peak_selection

- **CHIP_FIRST_001 / 首板+顶格筹码峰找庄**：1个月内首板更佳；涨停成交量较前日倍量以上。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。

## closing_intraday

- **CLOSE_001 / 收盘前半小时拉升**：全天运行平稳，尾市半小时连续大单扫盘，斜线上攻。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **CLOSE_002 / 收盘前半小时下跌**：全天平稳，尾市半小时大单小单一起砸，约45度下行。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **CLOSE_003 / 收盘前急拉拉尾**：收盘瞬间超大单直线拉升，中间无停顿，可能为次日出货做图形。输出：`RISK_ALERT`，风险：`medium`。
- **CLOSE_004 / 收盘前急跌打尾**：收盘瞬间超大单直线下跌，可能为次日拉升前震仓。输出：`WAIT_CONFIRMATION`，风险：`medium`。

## dealer_classification

- **CHIP_DEALER_001 / 强庄定性**：后三天平均收盘价大于首板涨停收盘价；股价不断上涨但成交量缩量，市场惜售。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **CHIP_DEALER_002 / 狡庄定性**：后三天平均收盘价小于首板收盘价但未跌破首板开盘价；后三天成交量缩量且不超过首板成交量。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **CHIP_DEALER_003 / 弱庄定性**：后三天平均收盘价跌破首板开盘价。输出：`AVOID_OR_WAIT`，风险：`medium`。

## gap_risk_pattern

- **GAP_001 / 连续跳空第三衰竭缺口**：连续跳空中第三个缺口高开幅度明显加大；接近顶部或主力急于兑现。输出：`RISK_ALERT`，风险：`high`。

## intraday_accumulation_wash_distribution

- **ACC_001 / 打压式吸筹**：价格一直在均线下方弱势运行，V型快速抬升且放量。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **ACC_002 / 吸筹拉升：创新高但量未创新高**：第二波上涨价格创新高但成交量未创新高，实为健康走势，堆量推动。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **ACC_003 / 吸筹拉升：一浪高过一浪且堆量**：价格一浪高过一浪，每次拉升都有堆量，低位时为进场候选。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **ACC_004 / 洗盘+拉升式吸筹**：前半段过山车式暴力洗盘，后半段堆量吸筹拉升。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **ACC_005 / 诱多式吸筹**：先放量拉一波，第二波缩量诱多，回落后后半段堆量上攻。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **WASH_004 / 试盘分时**：拉高回落，单峰量，日线量能放大并打到前压力位附近。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **WASH_005 / 跳空低开式洗盘**：跳空低开迅速下跌，低点后反弹横盘，反弹有放量承接。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **WASH_006 / 震荡式洗盘**：全天区间内上下波动无明确方向，用时间消磨耐心。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **DIST_004 / 早盘拉高缩量出货**：早盘迅速拉高，拉高缩量，随后价格缓慢下跌且无明显放量。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **DIST_005 / 台阶出货**：一浪低过一浪，每次下跌放大量/堆量，第二波放量创新低为离场信号。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **DIST_006 / 板上出货**：封涨停后多次炸板，炸板量能放大，午后跳水危险。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## intraday_buy_technique

- **IBUY_001 / 高开高走回调不破均价线**：高开高走，股价在均价线上方，回调不破黄线并勾头向上，MACD红柱。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **IBUY_002 / 高开低走击破均价线后快速修复**：高开不大，快速跌破均价线但下跌不放量，随后快速修复并站上均价线。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **IBUY_003 / 低开高走回调不破均价线**：缩量低开后逐步震荡上涨，拉升初期量柱减弱形成洗盘完成信号。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **IBUY_004 / 分时头肩底**：震荡下跌创新低后反弹并回到均价线上，头肩底再拉升到均价线时为候选。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **IBUY_005 / 分时草上飞**：股价在均价线上方震荡上涨，每次回调都不破均价线，量价匹配，异动量突破前高。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **IBUY_006 / 分时强控盘**：早盘放量拉升后维持均价线上方反复震荡，量能萎缩，多次下探不破均价线。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **IBUY_007 / 分时事不过三**：股价在均价线下方，多次上攻受压不超过3次，第4次带量突破站上均价线。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **IBUY_008 / 拉升回档承接**：10:30前放量突破重要阻力，快速拉升后回档有资金承接，卖一到卖五被吃掉，突破前高。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。

## intraday_indicator

- **INTRA_IND_001 / 分时MACD背离**：分时价格与MACD出现背离，用于辅助判断分时转折。输出：`WAIT_CONFIRMATION`，风险：`low`。
- **INTRA_IND_002 / MACD黏合起爆点**：MACD黏合后放量上攻，可能形成起爆点。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。

## intraday_indicator_confirmation

- **T_CONFIRM_001 / 做T配合即时MACD金叉/死叉**：12种做T形态结合即时MACD，金叉增强买点，死叉增强卖点。输出：`WAIT_CONFIRMATION`，风险：`low`。

## intraday_sell_technique

- **ISELL_001 / 分时头肩顶**：快速拉升后形成左肩、头部、右肩，跌破颈线位。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **ISELL_002 / 分时M头**：两次上攻受压，第二个勾头下探时。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **ISELL_003 / 快速上攻背离**：股价快速上攻不能封板，股价与均价线幅度超过3%，勾头时。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **ISELL_004 / 分时涨停炸板**：封单逐步减少或快速减少，炸板后反抽无力不能再封。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **ISELL_005 / 均价线压制卖出**：股价在均价线下方，每次触碰均价线就回调，4次以上不能突破。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **ISELL_006 / 分时向下闪电**：快速回调后弱反弹，再度跌破上一波低点形成向下闪电。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **ISELL_007 / 开盘拉升破均价线**：开盘快速放量拉升但未封板，抛压增多，勾头缩量后快速跌破均价线。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **ISELL_008 / 快速下跌反抽失败**：开盘快速下跌放量，反弹遇均价线/平台压制无法站上。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## intraday_t_filter

- **T_FILTER_001 / 白线跌破黄线且持续在黄线下方：原则不做T**：白色即时线跌破黄色均价线；持续在均价线下方运行。输出：`NO_TRADE`，风险：`medium`。

## intraday_t_mode

- **T_MODE_001 / 正向做T：先买后卖**：上午大幅低开或大幅下探；低位承接后等待日内反弹。输出：`SIM_BUY_CANDIDATE`，风险：`high`。
- **T_MODE_002 / 反向做T：先卖后买**：上午大幅高开或快速拉升；高位出现压力或回落风险。输出：`REDUCE_OR_EXIT`，风险：`high`。

## intraday_t_positive

- **T_POS_001 / 分时上穿均线并大幅放量**：价格上穿黄色均价线，同时成交量明显放大。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **T_POS_002 / 整理后突发急剧放量直线拉升**：整理区后突然放巨量，分时直线拉升，体现主力做多。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **T_POS_003 / 三次下行试探均线不破后放量上行**：三次回踩均价线不破，向上等待放量。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **T_POS_004 / 分时三底逐级抬升且量能配合**：三个日内低点逐级抬升，并有成交量配合。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **T_POS_005 / 快速俯冲后钩头放量上穿均线形成金叉**：急跌后快速钩头，放量上穿均线，MACD/均线金叉。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **T_POS_006 / 分时与均线平缓发散向上**：白线与均价线波动平缓、同步发散向上，趋势偏多。输出：`HOLD_OR_TRAIL`，风险：`medium`。

## intraday_t_reverse

- **T_NEG_001 / 围绕均价线上方运行但跌破均价线**：股价一直在均价线上方运行，不破则持有；一旦跌破为卖点。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **T_NEG_002 / 低开上冲翻红但量能萎缩**：低开后上冲翻红，量能持续萎缩，易形成分时高点。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **T_NEG_003 / 向上拉升时分时量不集中放大**：拉升过程中量能不齐，主力做多不坚决。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **T_NEG_004 / 快速拉升但量能不持续且均价线没跟上**：快速拉升后量能不持续，均价线未跟随，调头一刻为风险点。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **T_NEG_005 / 箱体沿线短线有利先出**：箱体上沿附近短线已有利润，先模拟止盈；中线以破位为退出条件。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **T_NEG_006 / 开盘长波下跌反弹无量**：开盘长波下跌，反弹无量，主力砸盘做空坚决。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## intraday_t_time_window

- **T_TIME_0950_1010 / 09:50-10:10 短期高点窗口**：容易产生短期高点；适合高抛或减仓观察。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **T_TIME_1010_1040 / 10:10-10:40 主力进场窗口**：若个股拉升且主力数据良好；可继续观察或持有。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **T_TIME_1110 / 11:10 急拉警惕窗口**：该时间急拉容易诱多；除非市场极强，否则不追。输出：`AVOID_OR_WAIT`，风险：`medium`。
- **T_TIME_1330_1400 / 13:30-14:00 观察窗口**：午后波动未明确；等待主力动作。输出：`WAIT_CONFIRMATION`，风险：`low`。
- **T_TIME_1400_1430 / 14:00-14:30 游资突袭窗口**：容易横向整理；也可能有游资拉动涨停。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **T_TIME_1430_1500 / 14:30-15:00 强弱分化窗口**：弱势行情易诱多；强势行情可能继续拉高吸引人气。输出：`RISK_ALERT`，风险：`medium`。

## kline_bottom_reversal

- **K_BOTTOM_001 / 早晨十字星**：跌势中阴线、十字星、阳线，阳线收盘深入阴线实体。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_002 / 早晨之星**：跌势中阴线、小阴/小阳、阳线，阳线收盘深入阴线实体。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_003 / 好友反攻**：跌势中大阴后大/中阳，阳线收盘与阴线收盘相同或接近。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_004 / 曙光初现**：跌势中大阴后大/中阳，阳线收盘深入阴线实体。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_005 / 旭日东升**：跌势中阳线开盘深入阴线实体，收盘超过阴线开盘。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_006 / 低位平底**：跌势中两根或多根K线最低价相同或相近。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_007 / 低位圆底**：跌势中多根K线构成圆弧，最后一根跳空上行确认。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_008 / 低位塔底**：跌势中大/中阴后连续小阴小阳，最后大阳确认。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_009 / 巨阳包阴**：跌势中第二根大/中阳包裹第一根阴线实体。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_BOTTOM_010 / 低位五档线**：跌势中第一根阴线后多根小阳/小阴处在第一根阴线收盘价附近。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。

## kline_single_shape

- **K_SINGLE_001 / 一字线**：涨停或跌停价开盘且全天基本同价成交，开收高低粘连。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **K_SINGLE_002 / 光头光脚阳线**：一路上涨至收盘，买方占绝对优势，极度强壮K线。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **K_SINGLE_003 / 光头光脚阴线**：一路下跌至收盘，卖方占绝对优势，恐慌抛出。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_SINGLE_004 / 光头阳线/锤头支撑**：下影线代表低位获得买方支撑，常见于底部或调整完毕。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_SINGLE_005 / 光脚阳线/倒锤头压力**：上影线代表上方抛压，上影越长抛压越重。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **K_SINGLE_006 / 无实体线/十字星**：开盘收盘接近，买卖力量不确定，常提示趋势可能变化。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **K_SINGLE_007 / T字线**：开收高相同，仅留长下影；不同位置含义不同，下跌后可能见底，上涨后可能见顶。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **K_SINGLE_008 / 倒T字线**：开收低粘连且留长上影，反弹失败，上方抛压重，下降含义强。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_SINGLE_009 / 大阳线/大阴线位置判断**：大阳线底部横盘后偏上涨，上涨途中可持有，高位大涨后谨慎；大阴线反向处理。输出：`WAIT_CONFIRMATION`，风险：`medium`。

## kline_top_reversal

- **K_TOP_001 / 黄昏十字星**：涨势中三根K线：阳线、十字星、阴线，第三根阴线深入第一根内部。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_002 / 黄昏之星**：涨势中阳线、小阳/小阴、阴线，第三根阴线深入第一根内部。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_003 / 淡友反攻**：涨势中阳线后阴线高开低走，收盘与前阳线收盘相同或相近。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_004 / 乌云压顶**：涨势中阳线后阴线高开低走，收盘深入第一根阳线实体。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_005 / 倾盆大雨**：涨势中第二根阴线低开低走，收盘低于第一根阳线开盘。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_006 / 高位平顶**：涨势中两根或多根K线最高价相同，提示上方压力。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_007 / 高位圆顶**：涨势中多根小阴小阳构成圆弧顶，跳空阴线确认。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_008 / 高位塔顶**：涨势中大/中阳后多根小阴小阳，最后大/中阴确立。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_009 / 巨阴包阳**：涨势中第二根阴线完全包裹第一根阳线实体。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_TOP_010 / 顶部双桨**：涨势中两根螺旋桨K线基本在同一水平线上。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## kline_trend_combo

- **K_UP_001 / 红三兵**：底部或涨势中三根阳线，收盘价节节升高。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_UP_002 / 高位盘旋**：上涨初期/中期大阳后多根小阴小阳，最低价高于大阳收盘价。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **K_UP_003 / 连续跳高**：跌势中多根阳线跳空高开，后市持续看涨。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_UP_004 / 五阳上阵**：跌势中多根阳线跳空高开，持续转强。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **K_DOWN_001 / 黑三兵**：涨势中三根阴线收盘价节节下降。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_DOWN_002 / 五阴连天**：顶部五根阴线收盘价节节下降。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_DOWN_003 / 低档排列**：顶部大/中阴后多根小阴小阳，最高价低于阴线最低价。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **K_DOWN_004 / 三级跳水**：顶部三根阴线，第一根跳空高开，后两根跳空低开。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## legacy_上涨阶段量价配合

- **LEGACY_VP_UP_001 / 价升量缩**：['大阳线', '中阳线', '小阳线']；三日上升但涨幅逐日变小，越涨越慢。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **LEGACY_VP_UP_002 / 放量滞涨**：['大阳线', '中阳线', '小阳线']；三日上涨但涨幅递减，价格滞涨。输出：`REDUCE_OR_EXIT`，风险：`high`。
- **LEGACY_VP_UP_003 / 缩量大涨**：['小阳线', '中阳线', '大阳线']；涨幅逐日加大，缩量加速上涨。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **LEGACY_VP_UP_004 / 放量大涨**：['小阳线', '中阳线', '大阳线']；三日上升且涨幅逐日加大。输出：`SIM_BUY_CANDIDATE`，风险：`medium_to_high`。

## legacy_下跌阶段量价配合

- **LEGACY_VP_DOWN_001 / 缩量小跌**：['大阴线', '中阴线', '小阴线']；三日下降但跌幅逐日减小，越跌越慢。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **LEGACY_VP_DOWN_002 / 放量小跌**：['大阴线', '中阴线', '小阴线']；三日下降但跌幅逐日变小。输出：`SIM_BUY_CANDIDATE`，风险：`medium_high`。
- **LEGACY_VP_DOWN_003 / 缩量大跌**：['小阴线', '中阴线', '大阴线']；跌幅逐日加大，加速下跌。输出：`AVOID_OR_WAIT`，风险：`high`。
- **LEGACY_VP_DOWN_004 / 放量大跌**：['小阴线', '中阴线', '大阴线']；跌幅逐日加大，价跌加速。输出：`REDUCE_OR_EXIT`，风险：`high`。

## legacy_分时图量价配合

- **LEGACY_VP_INTRADAY_001 / 分时下跌持续放量**：['分时连续下跌']；平开或盘整后持续下跌，跌幅扩大。输出：`REDUCE_OR_EXIT`，风险：`high`。
- **LEGACY_VP_INTRADAY_002 / 45度角放量下跌**：['午后45度角震荡下跌']；低位横盘后沿约45度角震荡下行，收于较低位置。输出：`REDUCE_OR_EXIT`，风险：`high`。
- **LEGACY_VP_INTRADAY_003 / 45度角放量拉升**：['午后45度角稳健攀升']；低开后小幅放量拉升，横盘后沿约45度角稳健上行。输出：`SIM_BUY_CANDIDATE`，风险：`medium_high`。
- **LEGACY_VP_INTRADAY_004 / 分时上升持续放量**：['分时持续上涨']；分时线在均价线上方运行后持续拉升，节节上涨。输出：`SIM_BUY_CANDIDATE`，风险：`medium_high`。

## legacy_单根K线量价

- **LEGACY_VP_SINGLE_001 / 放量大阳线**：['大阳线']；股价涨幅较大，实体大阳线。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **LEGACY_VP_SINGLE_002 / 缩量大阳线**：['大阳线']；股价大幅上涨。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **LEGACY_VP_SINGLE_003 / 放量大阴线**：['大阴线']；股价跌幅较大，实体大阴线。输出：`REDUCE_OR_EXIT`，风险：`high`。
- **LEGACY_VP_SINGLE_004 / 缩量大阴线**：['大阴线']；大幅下跌。输出：`AVOID_OR_WAIT`，风险：`high`。
- **LEGACY_VP_SINGLE_005 / 放量小阴小阳线**：['小阴线或小阳线']；实体小，股价波动小。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **LEGACY_VP_SINGLE_006 / 缩量小阴小阳线**：['小阴线或小阳线']；实体小，波动小。输出：`WAIT_CONFIRMATION`，风险：`low_to_medium`。
- **LEGACY_VP_SINGLE_007 / 放量中阳线/中阴线趋势延续**：['中阳线或中阴线']；中等实体，方向跟随当前趋势。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **LEGACY_VP_SINGLE_008 / 缩量中阴中阳线控盘信号**：['中阳线或中阴线']；中等实体，价格有波动。输出：`WAIT_CONFIRMATION`，风险：`medium_to_high`。

## legacy_平量阶段量价配合

- **LEGACY_VP_FLAT_001 / 平量滞涨**：['大阳线', '中阳线', '小阳线']；三日上涨但涨幅逐日减小，价格滞涨。输出：`REDUCE_OR_EXIT`，风险：`high`。
- **LEGACY_VP_FLAT_002 / 平量大涨**：['小阳线', '中阳线', '大阳线']；三日上涨且涨幅逐日扩大。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **LEGACY_VP_FLAT_003 / 平量价缩**：['大阴线', '中阴线', '小阴线']；三日下跌但跌幅变小，价格似乎止跌。输出：`AVOID_OR_WAIT`，风险：`high`。
- **LEGACY_VP_FLAT_004 / 平量大跌**：['小阴线', '中阴线', '大阴线']；三日下跌且跌幅逐日扩大，加速下跌。输出：`AVOID_OR_WAIT`，风险：`high`。

## limit_up_intraday_shape

- **LIMIT_001 / 斜刺型涨停**：斜刺型涨停形态，需结合封单强度、炸板次数、成交密度。输出：`WAIT_CONFIRMATION`，风险：`high`。
- **LIMIT_002 / 平台型涨停**：平台型涨停形态，需结合封单强度、炸板次数、成交密度。输出：`WAIT_CONFIRMATION`，风险：`high`。
- **LIMIT_003 / 箱体型涨停**：箱体型涨停形态，需结合封单强度、炸板次数、成交密度。输出：`WAIT_CONFIRMATION`，风险：`high`。
- **LIMIT_004 / 凹型涨停**：凹型涨停形态，需结合封单强度、炸板次数、成交密度。输出：`WAIT_CONFIRMATION`，风险：`high`。
- **LIMIT_005 / 脉冲型涨停**：脉冲型涨停形态，需结合封单强度、炸板次数、成交密度。输出：`WAIT_CONFIRMATION`，风险：`high`。
- **LIMIT_006 / 强势型涨停**：强势型涨停形态，需结合封单强度、炸板次数、成交密度。输出：`WAIT_CONFIRMATION`，风险：`high`。

## opening_3min_emotion

- **OPEN3_001 / 开盘三分钟买入一致**：第一分钟主动买盘大于卖盘为红柱，后两根连续红柱。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **OPEN3_002 / 开盘三分钟买入分歧**：第一分钟买盘大于卖盘，后续两根绿柱或红绿相间，存在诱多。输出：`RISK_ALERT`，风险：`medium`。
- **OPEN3_003 / 开盘三分钟卖出一致**：第一分钟主动买盘小于卖盘为绿柱，后两根连续绿柱。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **OPEN3_004 / 开盘三分钟卖出分歧**：第一分钟买盘小于卖盘，后续两根红柱或红绿相间，存在诱空承接。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。

## opening_intraday

- **OPEN_001 / 高开N型强势上攻**：高开后快速上攻、快速回落、再快速上冲，抛压后被买盘托起。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **OPEN_002 / 高开W型强势上攻**：高开后多一次探底，形成W型并恢复上攻。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **OPEN_003 / 高开三角形向上突破**：开盘窄幅三角形，10点前向上突破。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **OPEN_004 / 高开倒N型拉高出货**：高开后上冲回落，再上冲不过开盘价后回落。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **OPEN_005 / 低开N/W洗盘上攻**：低开后快速上冲至缺口附近，回落后再上攻回补缺口。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **OPEN_006 / 低开强行出货**：低开后继续低走，或冲到缺口附近后再回落且未回补缺口。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **OPEN_007 / 缺口无回补沿跳空方向运行**：跳空缺口开盘后没有任何回补动作，全天常沿跳空方向运行。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **OPEN_008 / 平开高走量能向上**：平开后股价上行放量，前三分钟外盘大于内盘。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **OPEN_009 / 平开低走量能向下**：平开后股价下行，前三分钟内盘大于外盘。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## orderbook_language

- **ORDER_001 / 压迫式挂单**：委卖栏三档以上大卖单，制造抛压，可能为拉升前试盘。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **ORDER_002 / 递增压迫式**：委卖第二档大于第一档、第三档大于第二档，暗示后方卖压增大。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **ORDER_003 / 递减压迫式**：第一档卖单最大，后两档依次减少；若第一档被吃掉，后续可能快速扫光。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **ORDER_004 / 拦截式挂单**：委买栏连续几档大买单，显示下方接盘巨大，重心不断上移。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **ORDER_005 / 一字形拦截式**：委买栏一档明显大接单，大中小盘需按盘口规模判断，若反复出现为长效暗示。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **ORDER_006 / 递增拦截式**：委买三档以上递增大接单，呈金字塔稳定感，显示主力实力。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **ORDER_007 / 夹板式挂单**：买卖盘口分别挂大单，上有天花板下有水泥板，成交限定在夹板空间。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **ORDER_008 / 蜂窝式挂单**：买卖栏密集连续大单，显示筹码丰富、买卖气氛热烈。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **ORDER_009 / 委卖蜂窝被吞没**：委卖栏蜂窝式挂单开始被吞没，涨停概率高于委买式蜂窝。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **ORDER_010 / 假密度小单密集成交**：挂单密度不大但小单密集成交，分时光滑，可能非主力主动买盘。输出：`AVOID_OR_WAIT`，风险：`medium`。

## ppt_volume_price_pattern

- **PPT_VP_001 / PPT放量大阳线**：大阳线且放量，买卖密集但买方更多，低位常解释为建仓吸筹。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **PPT_VP_002 / PPT缩量大阳线**：大阳线但缩量，卖压很少，主力高控盘/加速上涨。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **PPT_VP_003 / PPT放量大阴线**：大阴线且放量，高位多为出货和抛压巨大。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **PPT_VP_004 / PPT缩量大阴线**：大阴线但缩量，恐慌一致看空，下跌中继风险。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **PPT_VP_005 / PPT放量小阴小阳**：小实体且放量，趋势顶部或底部大分歧，预示可能反转。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **PPT_VP_006 / PPT缩量小阴小阳**：小实体且缩量，市场混沌无方向，可能继续横盘。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **PPT_VP_007 / PPT放量中阴中阳**：中等实体且放量，上升趋势中阳延续，下跌趋势中阴延续。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **PPT_VP_008 / PPT缩量中阴中阳**：中等实体且缩量，高控盘；上升中偏洗盘，高位横盘则背离风险。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **PPT_VP_009 / PPT价升量缩**：三日上涨但涨速变慢、成交量递减，买方动能减弱，短期或回调有限。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **PPT_VP_010 / PPT放量滞涨**：三日上涨但涨速变慢、量递增，抛压/分歧扩大，高位见顶风险。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **PPT_VP_011 / PPT平量滞涨**：三日上涨变慢但量持平，花费同代价涨得更慢，对手盘增大。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **PPT_VP_012 / PPT缩量大涨**：涨幅加速且量缩，主力锁仓/高控盘，直至巨量滞涨再风险提示。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **PPT_VP_013 / PPT放量大涨**：涨幅加速且量增，量价齐升，多方进攻，但爆巨量需警惕出货。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **PPT_VP_014 / PPT平量大涨**：涨幅加速但量持平/偏缩，抛压小，一致看涨，高控盘。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **PPT_VP_015 / PPT缩量小跌**：跌幅放缓且量减，卖盘减弱，常为洗盘变盘信号。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **PPT_VP_016 / PPT放量小跌**：跌幅放缓但量增，买方增强，大量资金承接，见底候选。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **PPT_VP_017 / PPT平量价缩**：跌势放缓但三根高量平量，抛压不弱，下跌中继弱反弹。输出：`AVOID_OR_WAIT`，风险：`medium`。
- **PPT_VP_018 / PPT缩量大跌**：跌幅加速且量减，恐慌一致看空，下跌中继风险。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **PPT_VP_019 / PPT放量大跌**：跌幅加速且量增，高位多为主力出货，持续下跌风险。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **PPT_VP_020 / PPT平量大跌**：跌幅加速但量平/缩，无承接，一致看空，下跌中继。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## risk_control_rule

- **CHIP_STOP_001 / 强庄/狡庄止损5-8个点**：强庄和狡庄策略设置5%-8%风险阈值。输出：`RISK_ALERT`，风险：`medium`。

## safety_boundary

- **SAFETY_001 / 所有策略仅限模拟/候选评分**：模型输出只能作为候选评分、概率判断或辅助解释，不得直接变成实盘下单命令。输出：`NO_TRADE`，风险：`high`。

## stock_selection_filter

- **VOLRATIO_001 / 量比选股过滤器**：涨幅大于3%且小于8%；量比大于1.5。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。

## training_safety

- **SAFETY_002 / 训练数据防未来函数/防泄漏**：训练集/验证集/测试集/样本外必须隔离，尽量使用walk-forward validation。输出：`NO_TRADE`，风险：`high`。

## turnover_feature

- **TURN_001 / 换手率低于3%普通/无大资金特征**：约70%股票日换手率低于3%，通常没有较大实力资金运作。输出：`WAIT_CONFIRMATION`，风险：`low`。
- **TURN_002 / 换手率3%-7%相对活跃**：换手率3%-7%，相对活跃，需要关注。输出：`WAIT_CONFIRMATION`，风险：`low`。
- **TURN_003 / 换手率7%-10%高度活跃**：强势股中常见，属于高度活跃状态。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **TURN_004 / 换手率10%-15%强庄大举运作**：若非历史高位/中长期顶部，10%-15%换手率可能为强庄大举运作。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **TURN_005 / 换手率超过15%且维持密集区**：超过15%后能够保持在当日密集成交区附近，可能具备强庄特征。输出：`SIM_BUY_CANDIDATE`，风险：`high`。

## turnover_position

- **TURN_006 / 低位高换手**：低位高换手可能有机构吸货，筹码从散户向机构集中。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **TURN_007 / 高位高换手**：高位高换手可能为机构对倒放量、派发高价筹码。输出：`REDUCE_OR_EXIT`，风险：`high`。

## volume_pillar

- **VPILLAR_001 / 低量柱**：阶段局部最低量柱，三日无更低量，成交清淡，常用于测试支撑/夯底/洗盘。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **VPILLAR_002 / 平量柱**：两根或多根量柱基本持平，可体现支撑压力；并肩平量偏温和上升，凹口平量偏大幅上升。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **VPILLAR_003 / 高量柱**：阶段局部最高量柱，若不能成为黄金柱后势多偏弱；温和梯量递增可为启动柱。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **VPILLAR_004 / 倍量柱**：当日量比前日高一倍或数倍，阳柱/假阴阳柱，常是主力介入抢筹或转折点。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **VPILLAR_005 / 缩量柱**：至少三根量柱逐步缩矮，表示惜售或缩至极限后可能反转，也可能调整在即。输出：`WAIT_CONFIRMATION`，风险：`medium`。

## volume_price_relation

- **VREL_001 / 底部放量上涨**：底部放量上涨，大资金开始买入，后续上涨概率增加。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **VREL_002 / 底部缩量上涨**：底部缩量上涨说明主力锁定筹码，高位放量则转为出货风险。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **VREL_003 / 放量下跌**：放量下跌，偏大资金出货。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **VREL_004 / 低位缩量下跌**：低位缩量下跌不确定，若空方能量释放完毕，可等待进场点。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **VREL_005 / 微量涨停**：买的人多但卖的人少，强势上涨信号。输出：`HOLD_OR_TRAIL`，风险：`medium`。
- **VREL_006 / 微量跌停**：一字跌停，卖的人多买的人少，需等待空方放量后再次缩量再找机会。输出：`RISK_ALERT`，风险：`medium`。
- **VREL_007 / 上涨途中缩量回调**：上涨趋势后缩量回调，说明大资金未明显离场；末期再次放量或触底反弹为确认。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **VREL_008 / 放量突破阻力位**：放量突破阻力位，阻力转支撑，继续上涨概率增加。输出：`SIM_BUY_CANDIDATE`，风险：`medium`。
- **VREL_009 / 上涨减速时缩量**：持续上涨后涨速减缓且量持续减少，筹码锁定但不适合追高。输出：`AVOID_OR_WAIT`，风险：`medium`。
- **VREL_010 / 顶部放量滞涨**：高位放量但股价不涨，主力卖出与散户追高并存，常为见顶信号。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **VREL_011 / 顶部放量杀跌**：高位突然放量杀跌，大资金卖出，见顶回调概率高。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **VREL_012 / 下跌途中缩量反弹**：下跌趋势中缩量反弹，多头乏力，无大资金介入，反弹后可能继续跌或震荡。输出：`AVOID_OR_WAIT`，风险：`medium`。
- **VREL_013 / 向下无量空跌**：持续下跌且低量，无明显买盘关注，持续下跌概率高。输出：`REDUCE_OR_EXIT`，风险：`medium`。

## wash_or_distribution_intraday

- **WASH_001 / U型洗盘**：高开-低走-再高收，大单打穿关键价，小单非密集成交，大单挂而不交。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **WASH_002 / 拱型洗盘**：低开-高走-再低收，小单拉高、大单打压，制造拉高出货假象。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **WASH_003 / U型+拱型复合洗盘**：先U后拱或先拱后U，意在同时洗获利盘和套牢盘，大单成交和上下压盘更频繁。输出：`WAIT_CONFIRMATION`，风险：`medium`。
- **DIST_001 / 拉高出货分时**：锯齿走势，小单拉高、大单打下，上方少挂大单，下方远处闪现大单。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **DIST_002 / 打低出货分时**：开盘快速拉高后一路卖出，大单小单一起下，坚决出局。输出：`REDUCE_OR_EXIT`，风险：`medium`。
- **DIST_003 / 锯齿形出货**：高位平台培养突破预期，成交不大、少大单、以小单分拆出货。输出：`REDUCE_OR_EXIT`，风险：`medium`。