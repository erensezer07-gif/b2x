"""API istek ve yanıt modelleri.

Veritabanı modelleriyle karıştırılmamalı: bunlar dışarıya açılan sözleşmedir.
Ayrı tutulmalarının somut sebebi `users.password_hash` — model onu taşır, hiçbir
yanıt modeli taşımaz (şartname M1).

Kullanıcıya gösterilecek metinler burada üretilmez. Eksik alan adları gibi
değerler İngilizce anahtar olarak döner, Türkçe karşılıkları arayüzde kurulur.
"""
