import unittest

from apps.stable.Tx_gui import build_xor_parity, crc16_ccitt
from apps.stable.Rx_gui import TransferState


class FECTests(unittest.TestCase):
    def test_recovers_one_missing_chunk(self):
        chunk_size = 8
        data = b"abcdefghABCDEFGH12345678tail"
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        parity = build_xor_parity(chunks, chunk_size)

        st = TransferState(1, 5, len(chunks), len(data), crc16_ccitt(data), "fec.bin")
        st.add_chunk(0, chunks[0])
        st.add_chunk(1, chunks[1])
        st.add_chunk(3, chunks[3])
        st.add_parity(0, len(chunks), chunk_size, parity)

        recovered = st.try_recover_from_parity(0)

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered[0], 2)
        self.assertEqual(recovered[1], chunks[2])
        self.assertTrue(st.complete())
        self.assertEqual(st.assemble(), data)
        self.assertEqual(crc16_ccitt(st.assemble()), st.file_crc)

    def test_does_not_recover_two_missing_chunks(self):
        chunk_size = 8
        data = b"abcdefghABCDEFGH12345678tail"
        chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
        parity = build_xor_parity(chunks, chunk_size)

        st = TransferState(2, 5, len(chunks), len(data), crc16_ccitt(data), "fec.bin")
        st.add_chunk(0, chunks[0])
        st.add_chunk(3, chunks[3])
        st.add_parity(0, len(chunks), chunk_size, parity)

        self.assertIsNone(st.try_recover_from_parity(0))
        self.assertFalse(st.complete())


if __name__ == "__main__":
    unittest.main()
