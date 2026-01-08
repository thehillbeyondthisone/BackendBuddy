import os
import ssl
from datetime import datetime, timedelta

def get_ssl_context(cert_file="cert.pem", key_file="key.pem"):
    """
    Ensure self-signed certs exist and return them.
    If they don't exist, generate them.
    """
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print(f"Generating self-signed certificate: {cert_file}, {key_file}")
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            
            # Generate key
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            
            # Generate cert
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, u"BackendBuddy"),
            ])
            
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=365)
            ).add_extension(
                x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
                critical=False,
            ).sign(key, hashes.SHA256())
            
            # Write key
            with open(key_file, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ))
                
            # Write cert
            with open(cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
                
            print("Certificate generated successfully.")
            
        except ImportError:
            print("WARNING: 'cryptography' library not found. Cannot generate certs.")
            print("Please run: pip install cryptography")
            return None, None
        except Exception as e:
            print(f"Error generating certs: {e}")
            return None, None

    return cert_file, key_file
