from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from emporio_agent.policy_guards import policy_response_issue
from emporio_agent.policy_calculations import simulate
from emporio_agent.policies import PolicyStore


class PolicyGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=PolicyStore(ROOT.parent/'data')

    def test_computed_discount_must_be_presented(self):
        result=simulate(self.store,'calcular_desconto',{'valor_brl':'800','desconto_percentual':'20','usar_pix':True})
        self.assertIsNotNone(policy_response_issue('','Não acumula PIX; fica o desconto de 20%.',[result]))
        self.assertIsNone(policy_response_issue('','De R$ 800,00 por R$ 640,00; não acumula PIX.',[result]))

    def test_mixed_payment_requires_honest_unknown_discount(self):
        result=simulate(self.store,'calcular_pagamento_misto',{'valor_brl':'2500','valor_pix_brl':'1000'})
        values='R$ 2.500,00: R$ 1.000,00 PIX e R$ 1.500,00 cartão. '
        self.assertIsNotNone(policy_response_issue('',values+'O desconto só se aplica ao pagamento total.',[result]))
        self.assertIsNone(policy_response_issue('',values+'O manual não especifica desconto PIX parcial; confirme com a equipe.',[result]))

    def test_installment_exception_cannot_be_omitted(self):
        result=self.store.lookup('pagamentos')
        self.assertIsNotNone(policy_response_issue('','Até três vezes sem valor mínimo.',[result]))
        self.assertIsNone(policy_response_issue('','Até três vezes sem valor mínimo, com exceção abaixo de R$ 50,00 a confirmar.',[result]))

    def test_numeric_promo_question_requires_calculation(self):
        result=self.store.lookup('promocoes')
        self.assertIsNotNone(policy_response_issue('Um violão de R$ 800 com 20% pode acumular PIX?','Não acumula.',[result]))
        self.assertIsNone(policy_response_issue('Quais são as regras de promoções?','Não acumula.',[result]))

    def test_company_phone_cannot_silently_replace_primary_whatsapp(self):
        result=self.store.lookup('empresa')
        self.assertIsNotNone(policy_response_issue('Onde fica?','WhatsApp (67) 3341-4444.',[result]))
        self.assertIsNone(policy_response_issue('Onde fica?','WhatsApp (67) 3321-4500.',[result]))

    def test_email_conflict_requires_acknowledgement(self):
        result=self.store.lookup('privacidade')
        self.assertIsNotNone(policy_response_issue('Como excluir?','Escreva para contato@emporiodamusica.com.br.',[result]))
        self.assertIsNone(policy_response_issue('Como excluir?','O manual apresenta grafias divergentes de e-mail; confirme pelo WhatsApp.',[result]))

    def test_sunday_return_must_respect_holidays(self):
        result=self.store.lookup('horarios')
        self.assertIsNotNone(policy_response_issue('E no domingo?','Voltamos segunda às 09:00.',[result]))
        self.assertIsNone(policy_response_issue('E no domingo?','Voltamos no próximo dia útil às 09:00.',[result]))

    def test_custom_exchange_rule_cannot_deny_every_online_return(self):
        result=self.store.lookup('devolucoes')
        question='Posso devolver um instrumento com regulagem personalizada?'
        self.assertIsNotNone(policy_response_issue(question,'Não. Itens personalizados não podem ser devolvidos.',[result]))
        self.assertIsNone(policy_response_issue(question,'A regra restringe trocas de itens personalizados. Devolução online exige análise da equipe; o manual não esclarece esse caso.',[result]))
        self.assertIsNone(policy_response_issue('Qual o prazo de devolução online?','São sete dias do recebimento.',[result]))

    def test_custom_return_requires_relevant_sections_even_after_wrong_tool(self):
        question='Posso devolver um instrumento com regulagem personalizada?'
        issue=policy_response_issue(question,'Não pode devolver porque não há como revender.',[self.store.lookup('escopo')])
        self.assertIn('consultar_politicas',issue)

    def test_defect_warranty_requires_procedure_distinction(self):
        result=self.store.lookup('garantia')
        question='Meu teclado apresentou defeito após 45 dias. Tenho garantia?'
        self.assertIsNotNone(policy_response_issue(question,'Sim, a garantia legal é de 90 dias.',[result]))
        self.assertIsNone(policy_response_issue(question,'A garantia legal de 90 dias permanece; a troca em até 30 dias segue o manual, e após isso a loja pode intermediar com o fabricante.',[result]))

    def test_national_shipping_does_not_inherit_local_fee(self):
        result=self.store.lookup('frete')
        self.assertIsNone(policy_response_issue('Qual o frete para Recife de um instrumento de R$ 450?','A cotação depende do CEP, peso e dimensões.',[result]))


if __name__=='__main__':
    unittest.main()
