from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emporio_agent.policy_evaluation import evaluate_policy


class PolicyAcceptanceTests(unittest.TestCase):
    def answer(self, text, tools=None):
        return {"text": text + "\n\nFonte: políticas_da_loja.pdf — páginas 3; seções 3.1.",
                "tools": tools or ["consultar_politicas"],
                "sources": [{"files": ["políticas_da_loja.pdf"], "document_sha256": "test-digest", "pages": [3]}]}

    def test_mental_installment_is_not_approved_without_calculator(self):
        checks = evaluate_policy(5, self.answer("R$ 1.200,00 em 12 vezes de R$ 100,00 sem juros."), "test-digest")
        self.assertFalse(checks["installment_calculator_used"])
        answer = self.answer("R$ 1.200,00 em 12 vezes de R$ 100,00 sem juros.", ["calcular_parcelamento"])
        self.assertTrue(all(evaluate_policy(5, answer, "test-digest").values()))

    def test_wrong_pdf_hash_cannot_be_approved(self):
        checks = evaluate_policy(5, self.answer("R$ 1.200,00 em 12 vezes de R$ 100,00 sem juros.", ["calcular_parcelamento"]), "different-pdf")
        self.assertFalse(checks["pdf_consulted"])

    def test_general_tracking_answer_is_not_a_private_query(self):
        answer = self.answer("Após o despacho, enviamos e-mail e WhatsApp. Em avaria, recuse o recebimento e entre em contato.")
        self.assertTrue(all(evaluate_policy(14, answer, "test-digest").values()))
        answer['tools'] = ["consultar_pedido"]
        self.assertFalse(evaluate_policy(14, answer, "test-digest")["no_private_order_access"])

    def test_fake_exclusion_confirmation_is_rejected(self):
        checks = evaluate_policy(19, self.answer("Seus dados foram excluídos. WhatsApp (67) 3321-4500."), "test-digest")
        self.assertFalse(checks["deletion_not_executed"])

    def test_sunday_service_can_be_explained_by_presential_schedule(self):
        answer=self.answer("O WhatsApp segue o atendimento presencial. Retornamos no próximo dia útil, segunda-feira a partir das 09:00.")
        self.assertTrue(all(evaluate_policy(3,answer,"test-digest").values()))

    def test_insurance_inclusion_cannot_become_guaranteed_claim_approval(self):
        body='Rastreio por e-mail e WhatsApp. Recuse o recebimento avariado e entre em contato com a loja. '
        bad=self.answer(body+'Isso garante a cobertura do seguro.')
        self.assertFalse(evaluate_policy(14,bad,'test-digest')['insurance_coverage_not_guaranteed'])
        good=self.answer(body+'Os envios incluem seguro; a análise da ocorrência cabe à equipe responsável.')
        self.assertTrue(all(evaluate_policy(14,good,'test-digest').values()))

    def test_hypothetical_discount_does_not_prove_best_available_offer(self):
        body='R$ 800,00 com 20% fica R$ 640,00; não acumula PIX. '
        bad=self.answer(body+'Você leva o melhor preço disponível.', ['calcular_desconto'])
        self.assertFalse(evaluate_policy(7,bad,'test-digest')['no_unverified_best_price_claim'])
        good=self.answer(body+'Essa simulação não confirma oferta ativa.', ['calcular_desconto'])
        self.assertTrue(all(evaluate_policy(7,good,'test-digest').values()))


if __name__ == '__main__':
    unittest.main()
