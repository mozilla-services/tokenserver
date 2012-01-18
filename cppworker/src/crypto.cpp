#include <iostream>

#include "libhose.h"
#include "cryptopp/hkdf.h"
#include "cryptopp/sha.h"
#include "cryptopp/osrng.h"
#include "response.pb.h"

using namespace CryptoPP;
using namespace powerhose;
using namespace std;

/**
 * Derive the given input keyring material into an output keyring material, 
 * using an automatically generated salt (which is returned as well)
 *
 **/
void _derive_secret(byte* ikm, byte* salt, byte* okm){
	int l = 82;
	const unsigned int BLOCKSIZE = 16* 8;

	// Get a random number from the OS
	byte random_salt[BLOCKSIZE];
	AutoSeededRandomPool rng;
	rng.GenerateBlock(random_salt, BLOCKSIZE);

	memcpy(salt, random_salt, BLOCKSIZE);
	
	// fill-in the result with 0 to start with
	memset(okm, 0, sizeof(okm));

	HMACKeyDerivationFunction<SHA256> hkdf;
	hkdf.DeriveKey(okm, l,
				   ikm, sizeof(ikm),
				   salt, sizeof(salt),
				   NULL, 0);
}

string derive_secret(string job, Registry reg) {
    // deserialize the request (XXX make sure we don't need anything more here)
    // 1. get the master certificate
    // XXX. for now this is a fixed value directly specified in the code, but
    // we want to have it on disk somewhere.
	byte ikm[80] = { 
		0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09,
		0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15,
		0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x21,
		0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d,
		0x2e, 0x2f, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39,
		0x3a, 0x3b, 0x3c, 0x3d, 0x3e, 0x3f, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45,
		0x46, 0x47, 0x48, 0x49, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f };

	byte salt[82];

	memset(salt, 0, sizeof(salt));
	byte okm[82];

    // 2. derivate it using HKDF
	_derive_secret(ikm, salt, okm);

    // 3. return the OKM and the salt
    Response resp;
    resp.set_salt(&salt, sizeof(salt));
    resp.set_secret(&okm, sizeof(okm));

    string string_resp;
    resp.SerializeToString(&string_resp);
    return string_resp;
}


int main(int argc, const char *argv[])
{
    // building the map of functions
    Function fderive = Function("derive_secret", &derive_secret);
    Functions functions;
    functions.insert(fderive);
  
    // running 10 workers
    return run_workers(10, functions, NULL, NULL);
}
