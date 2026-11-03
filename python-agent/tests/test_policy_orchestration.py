"""Falhas de seleção e respostas inseguras: valida o ciclo com dublê explícito."""
import unittest

from test_chat import ScriptedModel, call, text, DATA
from emporio_agent.agent import ConversationAgent
from emporio_agent.policy_guards import evidence_for_review
from emporio_agent.policies import PolicyStore


class PolicyOrchestrationTests(unittest.TestCase):
    def test_custom_return_retrieves_correct_source_and_falls_back_to_real_excerpts(self):
        model = ScriptedModel(
            call('consultar_escopo_loja'), text('Personalizados não podem ser devolvidos.'),
            call('consultar_politicas', {'topico':'devolucoes'}),
            text('Todo personalizado pode ser devolvido sem análise.'),
            text('Personalizados não podem ser devolvidos.'))
        answer = ConversationAgent(model, DATA).ask('Posso devolver um instrumento com regulagem personalizada?')
        self.assertTrue(model.requests[2][1], 'A fonte inadequada exige nova ferramenta.')
        self.assertIn('precisa de análise da equipe', answer.text)
        store = PolicyStore(DATA)
        for passage in store.lookup('devolucoes')['passages'][:2]:
            self.assertIn(passage['text'], answer.text)
        self.assertIn('Fonte: políticas_da_loja.pdf', answer.text)
        self.assertEqual(answer.tools, ['consultar_escopo_loja','consultar_politicas'])

    def test_shipping_policy_without_calculator_requires_new_tool(self):
        model = ScriptedModel(
            call('consultar_politicas', {'topico':'frete'}),
            text('O frete é R$ 35,00 e o prazo de 1 a 3 dias úteis.'),
            call('calcular_frete_local', {'valor_brl':'450'}),
            text('Frete de R$ 35,00; total de R$ 485,00; prazo estimado de 1 a 3 dias úteis.'))
        answer = ConversationAgent(model, DATA).ask('Moro em Campo Grande. Qual o frete para um instrumento de R$ 450?')
        self.assertTrue(model.requests[2][1])
        self.assertIn('calcular_frete_local', answer.tools)
        self.assertIn('R$ 485,00', answer.text)

    def test_review_cannot_invent_missing_excerpts(self):
        result = PolicyStore(DATA).lookup('escopo')
        self.assertIsNone(evidence_for_review([result], ('4.1','4.4')))


if __name__ == '__main__':
    unittest.main()
