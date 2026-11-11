import io
import json
import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from api.common import API
from api.rotas import validate
from api.historico import handler as History
from api.amadeus import Amadeus
from scripts import buscador_alertas as robot

class RoutesTest(unittest.TestCase):
    def data(self):
        return dict(apelido='Férias',origem='gyn',destino='MCZ',max_preco_alerta='950.00',ativo=True,
            data_inicio=date.today().isoformat(),data_fim=(date.today()+timedelta(days=3)).isoformat())
    def test_valid(self):
        row=validate(self.data())
        self.assertEqual(row[1],'GYN')
        self.assertEqual(row[3],Decimal('950.00'))
    def test_invalid(self):
        for changes in [dict(origem='Goiânia'),dict(destino='GYN'),dict(ativo='false'),dict(max_preco_alerta='NaN'),dict(max_preco_alerta='0'),dict(max_preco_alerta='1.001'),dict(data_fim=(date.today()+timedelta(days=31)).isoformat())]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate(self.data()|changes)
    def request(self, secret, auth):
        obj=object.__new__(API)
        obj.headers={'Authorization':auth}
        obj.reply=MagicMock()
        action=MagicMock(return_value={'ok':True})
        with patch.dict(os.environ,{'ADMIN_TOKEN':secret}):obj.dispatch(action)
        return obj,action
    def test_auth_denied(self):
        obj,action=self.request('secret','Bearer wrong')
        self.assertEqual(obj.reply.call_args.args[0],401);action.assert_not_called()
    def test_auth_missing_configuration(self):
        obj,action=self.request('','Bearer ')
        self.assertEqual(obj.reply.call_args.args[0],503);action.assert_not_called()
    def test_auth_ok(self):
        obj,action=self.request('secret','Bearer secret')
        self.assertEqual(obj.reply.call_args.args[0],200);action.assert_called_once()
    def test_history_days_rejected(self):
        obj=object.__new__(History);obj.path='/api/historico?dias=999'
        def dispatch(action):
            with self.assertRaises(ValueError):action()
        obj.dispatch=dispatch;obj.do_GET()

class ProviderTest(unittest.TestCase):
    def test_cheapest_brl(self):
        provider=Amadeus()
        provider.get=MagicMock(return_value=[{'price':{'currency':'BRL','grandTotal':'900.00'}},{'price':{'currency':'BRL','grandTotal':'800.20'}},{'price':{'currency':'USD','grandTotal':'1'}}])
        self.assertEqual(provider.cheapest('GYN','MCZ',date.today()),Decimal('800.20'))
    def test_empty(self):
        provider=Amadeus();provider.get=MagicMock(return_value=[])
        self.assertIsNone(provider.cheapest('GYN','MCZ',date.today()))

class RobotTest(unittest.TestCase):
    def run_robot(self, price=Decimal('800'), recent=None, sending=True):
        route=dict(id=1,apelido='Férias',origem='GYN',destino='MCZ',max_preco_alerta=Decimal('950'),ativo=True,data_inicio=date.today(),data_fim=date.today()+timedelta(days=1))
        conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect=[{'locked':True},route,{'id':7},recent]
        cur.fetchall.return_value=[route]
        env={k:'test' for k in ('DATABASE_URL','AMADEUS_CLIENT_ID','AMADEUS_CLIENT_SECRET','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID')}
        with patch.dict(os.environ,env),patch.object(robot,'db',return_value=conn),patch.object(robot,'Amadeus') as provider,patch.object(robot,'telegram',return_value=sending) as send:
            provider.return_value.cheapest.return_value=price
            if not sending:
                with self.assertRaises(RuntimeError):robot.run()
            else:robot.run()
            self.assertEqual(provider.return_value.cheapest.call_count,2)
        conn.close.assert_called_once()
        return cur,send
    def test_alert_saved_after_delivery(self):
        cur,send=self.run_robot();send.assert_called_once()
        self.assertIn('UPDATE historico_precos',cur.execute.call_args.args[0])
    def test_cooldown(self):
        _,send=self.run_robot(recent={'id':2});send.assert_not_called()
    def test_no_offer_not_saved(self):
        cur,send=self.run_robot(price=None);send.assert_not_called()
        self.assertFalse(any('INSERT' in call.args[0] for call in cur.execute.call_args_list))
    def test_delivery_failure_no_success_stamp(self):
        cur,send=self.run_robot(sending=False);send.assert_called_once()
        self.assertFalse(any('UPDATE historico_precos' in call.args[0] for call in cur.execute.call_args_list))

if __name__=='__main__':unittest.main()
